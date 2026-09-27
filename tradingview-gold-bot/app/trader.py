"""
ما يُفعل بالإشارة بعد فهمها.

هنا يلتقي كل شيء: حارس التكرار، وحدود الأمان، وحساب الوقف والهدف
من سعر التنفيذ الفعلي، ثم أمر الوسيط. وكل قرار يُسجَّل بسببه، فإن
لم تُفتح صفقة عُرف لماذا بالضبط.
"""

import logging

from app import risk
from app.brokers.base import BrokerError
from app.risk import RiskError
from app.dedupe import Dedupe
from app.signals import (BUY, CLOSE, ENTRY_KINDS, SELL, SL_HIT, TP1, TP2, TP3,
                         TP_ANY, TP_KINDS)

log = logging.getLogger("bridge.trader")


class Trader:
    def __init__(self, settings, broker, notifier=None, dedupe=None):
        self.settings = settings
        self.broker = broker
        self.notifier = notifier
        self.dedupe = dedupe or Dedupe()

    # ── المدخل ──

    def handle(self, signal):
        if not self.settings.enabled:
            return self._skip(signal, "البريدج موقوف: ENABLED=false")

        refusal = self._wrong_timeframe(signal)
        if refusal:
            return self._skip(signal, refusal)

        if not self.dedupe.check_and_add(signal.fingerprint()):
            return self._skip(signal, "تنبيه مكرر وصل مرة أخرى")

        if signal.kind in ENTRY_KINDS:
            return self._open(signal)
        if signal.kind in TP_KINDS or signal.kind == SL_HIT:
            if self.settings.legs:
                # كل رجل تحمل هدفها ووقفها عند الوسيط، فهو الذي يغلقها
                # — أسرع من أي تنبيه ولا ينقطع. وتنبيهٌ يتدخل هنا قد
                # يغلق رجلاً قُصد لها أن تجري إلى هدفها الأبعد.
                return self._skip(
                    signal, "الخروج بيد الوسيط ما دامت LEGS مضبوطة"
                )
        if signal.kind in (TP1, TP_ANY):
            return self._on_first_target(signal)
        if signal.kind == TP2:
            return self._protect(signal, "بلغ الهدف الثاني")
        if signal.kind == TP3:
            return self._close_all(signal, "بلغ الهدف الثالث")
        if signal.kind == SL_HIT:
            return self._on_stop(signal)
        if signal.kind == CLOSE:
            return self._close_all(signal, "أمر إغلاق")
        return self._skip(signal, f"نوع لا يُدار: {signal.kind}")

    def _wrong_timeframe(self, signal):
        """
        سبب الردّ إن لم يكن الفريم مسموحاً، وإلا لا شيء.

        وفريمٌ لم يصل يُردّ أيضاً ما دام الحدّ مضروباً: أن نفتح صفقة
        لا نعرف من أي فريم جاءت أخطر من أن نردّ تنبيهاً ناقصاً —
        والردّ يقول ما ينقص بالضبط فيُصلَح من أول مرة.
        """
        allowed = self.settings.allowed_timeframes
        if not allowed:
            return None

        names = "، ".join(str(m) for m in sorted(allowed))
        if signal.timeframe is None:
            return (
                f"التنبيه لا يحمل فريمه، والمسموح {names} دقيقة. "
                'أضف "tf":"{{interval}}" إلى رسالة التنبيه.'
            )
        if signal.timeframe not in allowed:
            return (
                f"فريم {signal.timeframe} دقيقة غير مسموح — المسموح {names}."
            )
        return None

    # ── فتح الصفقة ──

    def _open(self, signal):
        settings = self.settings
        symbol = settings.broker_symbol(signal.ticker)
        side = risk.side_of(signal)

        # الوسيط الورقي لا سوق له: نعطيه سعر التنبيه ليحاكي التنفيذ
        if hasattr(self.broker, "set_price") and signal.entry:
            self.broker.set_price(symbol, signal.entry)

        risk.check_distance(
            signal.risk_distance, settings.min_stop_distance, settings.max_stop_distance
        )

        self._risk_distance = signal.risk_distance
        info = self.broker.symbol_info(symbol)
        legs = self._legs(info)
        open_positions = self.broker.positions(symbol=symbol, magic=settings.magic)

        same_side = [p for p in open_positions if p.side == side]
        if same_side:
            return self._skip(signal, f"صفقة {side} مفتوحة أصلاً على {symbol}")

        against = [p for p in open_positions if p.side != side]
        if against:
            if not settings.reverse_on_opposite:
                return self._skip(signal, "صفقة معاكسة مفتوحة و REVERSE_ON_OPPOSITE=false")
            for position in against:
                self.broker.close(position)
                log.info("أُغلقت الصفقة المعاكسة %s قبل عكس الاتجاه", position.ticket)
            open_positions = self.broker.positions(symbol=symbol, magic=settings.magic)

        if len(open_positions) + len(legs) > settings.max_open_positions:
            return self._skip(
                signal,
                f"{len(legs)} صفقة تتجاوز حد المفتوحة ({settings.max_open_positions})",
            )

        # الخسارة تُحسب على الأرجل مجتمعة وتُفحص قبل فتح أيٍّ منها:
        # رجلٌ وحدها قد تمرّ والمجموع يتجاوز ما يحتمله الحساب.
        total_lot = round(sum(lot for _, lot in legs), 8)
        money = risk.check_money_at_risk(
            signal.risk_distance, total_lot, info.value_per_price_unit,
            settings.max_risk_usd,
        )

        opened, failures = [], []
        for target, lot in legs:
            try:
                opened.append(self._open_leg(signal, symbol, side, target, lot))
            except (BrokerError, RiskError) as exc:
                # رجلٌ سقطت وأخرى قامت: لا يُتراجع عن القائمة — إغلاقها
                # بخسارة السبريد أسوأ من تركها بوقفها — بل يُخبَر صاحبها.
                log.error("تعذّر فتح رجل الهدف %s: %s", target, exc)
                failures.append({"target": target, "lot": lot, "reason": str(exc)})

        if not opened:
            raise BrokerError(
                f"لم تُفتح أي صفقة: {failures[0]['reason'] if failures else 'سبب مجهول'}"
            )

        summary = {
            "status": "opened",
            "kind": signal.kind,
            "symbol": symbol,
            "side": side,
            "legs": opened,
            "risk_distance": round(signal.risk_distance, info.digits),
            "risk_usd": round(money, 2),
        }
        if failures:
            summary["failed_legs"] = failures

        self._announce(self._opened_text(side, symbol, opened, money, failures))
        log.info("فُتحت %s صفقة: %s", len(opened), summary)
        return summary

    def _open_leg(self, signal, symbol, side, target, lot):
        """صفقة واحدة بهدفها. يُعاد قراءة السعر لكل رجل فقد تحرّك."""
        info = self.broker.symbol_info(symbol)
        reward = risk.pick_reward_distance(signal, target)
        estimate = info.entry_price(side)
        sl_estimate, tp_estimate = risk.stop_and_target(
            side, estimate, signal.risk_distance, reward,
            digits=info.digits, broker_min_distance=info.stops_distance,
        )

        # الوقف يُرسل مع الأمر لا بعده: لحظة واحدة بلا وقف مخاطرة
        # لا داعي لها. ثم يُصحَّح على سعر التنفيذ الحقيقي.
        position = self.broker.market_order(
            symbol, side, lot,
            sl=sl_estimate, tp=tp_estimate,
            comment=f"TV {signal.kind} TP{target}",
            magic=self.settings.magic,
        )
        corrected = self._correct_after_fill(position, signal, info, reward)
        return {
            "target_tp": target,
            "lot": lot,
            "ticket": position.ticket,
            "fill": position.price_open,
            "sl": corrected["sl"],
            "tp": corrected["tp"],
            "corrected": corrected["changed"],
        }

    def _legs(self, info):
        """أرجل الإشارة: ما ضُبط في LEGS، وإلا صفقة واحدة بـ LOT."""
        settings = self.settings
        raw = settings.legs or [(settings.target_tp, self._single_lot(info))]
        volume_max = min(info.volume_max, settings.max_lot)
        return [
            (target, risk.normalize_lot(
                lot, volume_step=info.volume_step,
                volume_min=info.volume_min, volume_max=volume_max))
            for target, lot in raw
        ]

    def _single_lot(self, info):
        """حجم الصفقة الواحدة: من نسبة المخاطرة إن طُلبت، وإلا LOT."""
        settings = self.settings
        if settings.risk_percent <= 0:
            return settings.lot
        return risk.lot_for_risk(
            self.broker.balance(), settings.risk_percent, self._risk_distance,
            info.value_per_price_unit,
            volume_step=info.volume_step,
            volume_min=info.volume_min,
            volume_max=min(info.volume_max, settings.max_lot),
        )

    def _opened_text(self, side, symbol, opened, money, failures):
        head = f"فُتحت {len(opened)} صفقة {'شراء' if side == 'buy' else 'بيع'} على {symbol}"
        lines = [head]
        for leg in opened:
            lines.append(
                f"• {leg['lot']} هدفها TP{leg['target_tp']} — "
                f"تنفيذ {leg['fill']} · وقف {leg['sl']} · هدف {leg['tp'] or 'بلا'}"
            )
        lines.append(f"الخسارة عند الوقف {money:.2f} دولاراً للمجموع")
        for failed in failures:
            lines.append(f"⚠️ لم تُفتح رجل TP{failed['target']}: {failed['reason']}")
        return "\n".join(lines)

    def _correct_after_fill(self, position, signal, info, reward):
        """
        الوقف والهدف يُقاسان من سعر التنفيذ الفعلي.

        بين إرسال التنبيه وتنفيذه يتحرك الذهب، وقد يزيد الانزلاق.
        فما أُرسل مع الأمر كان تقديراً على السعر المعروض، وهنا
        يُصحَّح ليصير بُعد الوقف هو بُعد المؤشر بالضبط.
        """
        sl, tp = risk.stop_and_target(
            position.side, position.price_open, signal.risk_distance, reward,
            digits=info.digits, broker_min_distance=info.stops_distance,
        )
        tolerance = max(info.point, 10 ** -info.digits)
        needs = (abs((position.sl or 0.0) - sl) > tolerance
                 or (tp and abs((position.tp or 0.0) - tp) > tolerance))
        if not needs:
            return {"sl": position.sl, "tp": position.tp or None, "changed": False}
        try:
            updated = self.broker.modify(position, sl=sl, tp=tp)
            return {"sl": updated.sl, "tp": updated.tp or None, "changed": True}
        except BrokerError as exc:
            # الصفقة مفتوحة ومحمية بوقف التقدير: نُبقيها ونُخبر
            log.warning("تعذّر تصحيح الوقف بعد التنفيذ: %s", exc)
            self._announce(f"⚠️ تعذّر تصحيح وقف الصفقة {position.ticket}: {exc}")
            return {"sl": position.sl, "tp": position.tp or None, "changed": False}

    def _lot_for(self, signal, info):
        settings = self.settings
        if settings.risk_percent > 0:
            lot = risk.lot_for_risk(
                self.broker.balance(), settings.risk_percent, signal.risk_distance,
                info.value_per_price_unit,
                volume_step=info.volume_step,
                volume_min=info.volume_min,
                volume_max=min(info.volume_max, settings.max_lot),
            )
        else:
            lot = settings.lot
        lot = risk.normalize_lot(
            lot,
            volume_step=info.volume_step,
            volume_min=info.volume_min,
            volume_max=min(info.volume_max, settings.max_lot),
        )
        return lot

    # ── إدارة الصفقة بعد فتحها ──

    def _positions_of(self, signal):
        symbol = self.settings.broker_symbol(signal.ticker)
        return symbol, self.broker.positions(symbol=symbol, magic=self.settings.magic)

    def _on_first_target(self, signal):
        settings = self.settings
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"بلغ الهدف الأول ولا صفقة مفتوحة على {symbol}")

        info = self.broker.symbol_info(symbol)
        acted = []
        for position in positions:
            if settings.tp1_close_percent > 0:
                part = risk.normalize_lot(
                    position.volume * settings.tp1_close_percent / 100.0,
                    volume_step=info.volume_step,
                    volume_min=info.volume_min,
                    volume_max=position.volume,
                )
                if part < position.volume:
                    self.broker.close(position, volume=part)
                    acted.append(f"أُغلق {part} من {position.ticket}")
                    position = self.broker.positions(symbol=symbol, magic=settings.magic)
                    position = position[0] if position else None
                    if position is None:
                        continue

            if settings.tp1_move_to_breakeven:
                stop = risk.breakeven_stop(position.side, position.price_open, info.digits)
                self.broker.modify(position, sl=stop)
                acted.append(f"نُقل وقف {position.ticket} إلى الدخول {stop}")

        summary = {"status": "managed", "kind": signal.kind, "symbol": symbol,
                   "actions": acted}
        if acted:
            self._announce("بلغ الهدف الأول:\n" + "\n".join(acted))
        log.info("إدارة عند الهدف الأول: %s", summary)
        return summary

    def _protect(self, signal, reason):
        """تأمين الصفقة بنقل وقفها إلى الدخول إن لم يكن هناك."""
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"{reason} ولا صفقة مفتوحة على {symbol}")

        info = self.broker.symbol_info(symbol)
        acted = []
        for position in positions:
            stop = risk.breakeven_stop(position.side, position.price_open, info.digits)
            already = (position.is_buy and position.sl >= stop) or \
                      (not position.is_buy and 0 < position.sl <= stop)
            if already:
                continue
            self.broker.modify(position, sl=stop)
            acted.append(f"نُقل وقف {position.ticket} إلى {stop}")

        if acted:
            self._announce(f"{reason}:\n" + "\n".join(acted))
        return {"status": "managed", "kind": signal.kind, "symbol": symbol,
                "actions": acted}

    def _close_all(self, signal, reason):
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"{reason} ولا صفقة مفتوحة على {symbol}")
        closed = []
        for position in positions:
            self.broker.close(position)
            closed.append(position.ticket)
        self._announce(f"{reason}: أُغلقت الصفقات {closed}")
        log.info("%s: أُغلقت %s", reason, closed)
        return {"status": "closed", "kind": signal.kind, "symbol": symbol,
                "tickets": closed}

    def _on_stop(self, signal):
        """
        تنبيه ضرب الوقف.

        وقف الوسيط أسرع من أي تنبيه، فالصفقة مغلقة غالباً قبل وصوله.
        وإن بقيت مفتوحة — لأن سعر جست ماركتس تخلّف عن سعر الشارت —
        فهذه شبكة الأمان الأخيرة.
        """
        symbol, positions = self._positions_of(signal)
        if not positions:
            return {"status": "noop", "kind": signal.kind, "symbol": symbol,
                    "reason": "ضُرب الوقف والصفقة مغلقة أصلاً"}
        return self._close_all(signal, "تنبيه ضرب الوقف والصفقة ما زالت مفتوحة")

    # ── أدوات ──

    def _skip(self, signal, reason):
        log.info("لم تُنفَّذ [%s]: %s", signal.kind, reason)
        return {"status": "skipped", "kind": signal.kind, "reason": reason}

    def _announce(self, text):
        prefix = "🧪 تجريبي\n" if self.settings.dry_run else ""
        if self.notifier:
            self.notifier.send(prefix + text)
