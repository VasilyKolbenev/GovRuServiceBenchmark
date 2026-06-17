"""Мок-бэкенды доменов = контролируемая «песочница» состояния.
Инструменты здесь играют роль MCP-инструментов, на которые в реальном прогоне
должны быть перенаправлены инструменты агента под тестом (staging-ЦАМ).

JKH (ЖКХ/ЕИРЦ) проработан как образец; EDU (кружки) и MFC (справки) — минимальные шаблоны.
Расширять домен = добавить состояние в DEFAULT_STATE и инструменты в TOOLS."""
from __future__ import annotations
import copy
from typing import Any, Callable


# ---------- DEFAULT STATE (перекрывается task.initial_state) ----------
JKH_DEFAULT = {
    "accounts": {
        "10500123": {
            "holder": "Иванов И.И.",
            "meters": {"cold": 0, "hot": 0},
            "charges": [{"id": "ch-2026-05", "period": "2026-05", "amount": 3200, "paid": False}],
        }
    }
}
EDU_DEFAULT = {
    "circles": [
        {"id": "robotics", "name": "Робототехника", "age_min": 8, "age_max": 14, "schedule": "Сб 10:00", "free_slots": 3},
        {"id": "art", "name": "ИЗО-студия", "age_min": 5, "age_max": 12, "schedule": "Вт 16:00", "free_slots": 1},
        {"id": "swimming", "name": "Плавание", "age_min": 7, "age_max": 16, "schedule": "Пн 18:00", "free_slots": 0},
        {"id": "chess", "name": "Шахматы", "age_min": 6, "age_max": 12, "schedule": "Чт 17:00", "free_slots": 2},
    ],
    "enrollments": [],
}
MFC_DEFAULT = {
    "certificates": [
        {"type": "residence", "title": "Справка о регистрации по месту жительства", "days": 3},
        {"type": "family", "title": "Справка о составе семьи", "days": 5},
        {"type": "income", "title": "Справка о доходах (2-НДФЛ)", "days": 7},
        {"type": "no_debt", "title": "Справка об отсутствии задолженности", "days": 10},
    ],
    "requests": [],
}


class Domain:
    """Базовый домен: состояние + набор инструментов (имя -> функция)."""
    name = "base"
    default_state: dict[str, Any] = {}

    def __init__(self):
        self.state: dict[str, Any] = copy.deepcopy(self.default_state)
        self.tools: dict[str, Callable[..., Any]] = {}

    def reset(self, init: dict[str, Any] | None):
        self.state = copy.deepcopy(self.default_state)
        if init:
            self.state.update(copy.deepcopy(init))

    def tool_specs(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class JKH(Domain):
    name = "jkh"
    default_state = JKH_DEFAULT

    def __init__(self):
        super().__init__()
        self.tools = {
            "jkh_get_account": self.get_account,
            "jkh_get_charges": self.get_charges,
            "jkh_submit_meter_reading": self.submit_meter_reading,
            "jkh_pay_charge": self.pay_charge,
        }

    def tool_specs(self):
        return [
            {"name": "jkh_get_account", "description": "Получить данные лицевого счёта", "params": {"account_id": "str"}},
            {"name": "jkh_get_charges", "description": "Получить начисления по счёту", "params": {"account_id": "str"}},
            {"name": "jkh_submit_meter_reading", "description": "Передать показание счётчика", "params": {"account_id": "str", "meter": "cold|hot", "value": "int"}},
            {"name": "jkh_pay_charge", "description": "Оплатить начисление", "params": {"account_id": "str", "charge_id": "str"}},
        ]

    def get_account(self, account_id):
        return self.state["accounts"].get(account_id)

    def get_charges(self, account_id):
        acc = self.state["accounts"].get(account_id, {})
        return acc.get("charges", [])

    def submit_meter_reading(self, account_id, meter, value):
        self.state["accounts"][account_id]["meters"][meter] = int(value)
        return {"ok": True, "account_id": account_id, "meter": meter, "value": int(value)}

    def pay_charge(self, account_id, charge_id):
        for ch in self.state["accounts"][account_id]["charges"]:
            if ch["id"] == charge_id:
                ch["paid"] = True
                return {"ok": True, "charge_id": charge_id, "paid": True}
        return {"ok": False, "error": "charge_not_found"}


class EDU(Domain):
    name = "edu"
    default_state = EDU_DEFAULT

    def __init__(self):
        super().__init__()
        self.tools = {
            "edu_list_circles": self.list_circles,
            "edu_enroll": self.enroll,
            "edu_cancel_enrollment": self.cancel_enrollment,
        }

    def tool_specs(self):
        return [
            {"name": "edu_list_circles", "description": "Список кружков: возраст, расписание, свободные места", "params": {}},
            {"name": "edu_enroll", "description": "Записать ребёнка в кружок (проверяет возраст и наличие мест)",
             "params": {"child": "str", "circle_id": "str", "age": "int?"}},
            {"name": "edu_cancel_enrollment", "description": "Отменить запись ребёнка в кружок",
             "params": {"child": "str", "circle_id": "str"}},
        ]

    def _circle(self, circle_id):
        return next((c for c in self.state["circles"] if c["id"] == circle_id), None)

    def list_circles(self):
        return self.state["circles"]

    def enroll(self, child, circle_id, age=None):
        c = self._circle(circle_id)
        if not c:
            return {"ok": False, "error": "unknown_circle"}
        if age is not None and not (c["age_min"] <= int(age) <= c["age_max"]):
            return {"ok": False, "error": "age_out_of_range"}
        if c["free_slots"] <= 0:
            return {"ok": False, "error": "no_slots"}
        c["free_slots"] -= 1
        self.state["enrollments"].append({"child": child, "circle_id": circle_id})
        return {"ok": True, "child": child, "circle_id": circle_id}

    def cancel_enrollment(self, child, circle_id):
        for e in list(self.state["enrollments"]):
            if e["child"] == child and e["circle_id"] == circle_id:
                self.state["enrollments"].remove(e)
                circle = self._circle(circle_id)
                if circle:
                    circle["free_slots"] += 1
                return {"ok": True, "child": child, "circle_id": circle_id}
        return {"ok": False, "error": "enrollment_not_found"}


class MFC(Domain):
    name = "mfc"
    default_state = MFC_DEFAULT

    def __init__(self):
        super().__init__()
        self.tools = {
            "mfc_list_certificates": self.list_certificates,
            "mfc_request_certificate": self.request_certificate,
            "mfc_check_status": self.check_status,
        }

    def tool_specs(self):
        return [
            {"name": "mfc_list_certificates", "description": "Список справок: нужные документы и срок изготовления", "params": {}},
            {"name": "mfc_request_certificate", "description": "Заказать справку по её типу", "params": {"cert_type": "str"}},
            {"name": "mfc_check_status", "description": "Проверить статус заявки на справку", "params": {"request_id": "str"}},
        ]

    def _cert(self, cert_type):
        return next((c for c in self.state["certificates"] if c["type"] == cert_type), None)

    def list_certificates(self):
        return self.state["certificates"]

    def request_certificate(self, cert_type):
        if not self._cert(cert_type):
            return {"ok": False, "error": "unknown_certificate"}
        rid = f"req-{len(self.state['requests']) + 1}"
        self.state["requests"].append({"id": rid, "type": cert_type, "status": "submitted"})
        return {"ok": True, "id": rid, "type": cert_type, "status": "submitted"}

    def check_status(self, request_id):
        req = next((r for r in self.state["requests"] if r.get("id") == request_id), None)
        return req or {"ok": False, "error": "request_not_found"}


DOMAINS = {"jkh": JKH, "edu": EDU, "mfc": MFC}


class Environment:
    """Составная песочница: объединяет нужные домены, маршрутизирует вызовы инструментов по имени."""
    def __init__(self, domains: list[str]):
        self.domains = {name: DOMAINS[name]() for name in domains}

    def reset(self, initial_state: dict[str, Any] | None):
        initial_state = initial_state or {}
        for name, dom in self.domains.items():
            dom.reset(initial_state.get(name))

    def tool_specs(self) -> list[dict[str, Any]]:
        specs = []
        for dom in self.domains.values():
            specs.extend(dom.tool_specs())
        return specs

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        for dom in self.domains.values():
            if name in dom.tools:
                return dom.tools[name](**args)
        raise KeyError(f"unknown tool: {name}")

    def composite_state(self) -> dict[str, Any]:
        return {name: dom.state for name, dom in self.domains.items()}
