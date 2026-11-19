"""Run via: python run.py (launches both the SSE server and this Streamlit app)."""
from __future__ import annotations

import inspect
import json
import re

import streamlit as st

from clinical_mcp.client.router import SOURCES, REMOTE_URL, execute
from clinical_mcp.client.validation import unwrap_schema, local_defaults, display_default

st.set_page_config(page_title="Clinical MCP Lab", page_icon="🩺", layout="wide")


def error_details(exc: BaseException) -> str:
    """Show the real errors nested inside anyio TaskGroup ExceptionGroups."""
    if isinstance(exc, BaseExceptionGroup):
        details = [error_details(child) for child in exc.exceptions]
        return "; ".join(dict.fromkeys(details))
    summary = f"{type(exc).__name__}: {exc}"
    if exc.__cause__ is not None:
        return f"{summary} — причина: {error_details(exc.__cause__)}"
    return summary

def input_widget(name: str, meta: dict, required: bool, prefix: str, default=None):
    real = unwrap_schema(meta)
    label = meta.get("title") or name.replace("_", " ")
    if required:
        label += " *"
    help_text = meta.get("description") or ""
    typ = real.get("type", "string")
    placeholder = f"По умолчанию: {display_default(default)}" if default is not None else None
    if default is not None and typ == "boolean":
        help_text = (help_text + " · " if help_text else "") + placeholder
    widget_key = f"{prefix}:{name}"
    if "enum" in real:
        options = real["enum"]
        return st.selectbox(label, options=options, index=None,
                            placeholder=placeholder or "Выберите значение", help=help_text, key=widget_key)
    if typ == "boolean":
        return st.checkbox(label, value=bool(default) if default is not None else False,
                           help=help_text, key=widget_key)
    if typ in ("integer", "number"):
        # Empty value keeps the advertised fallback visible as a placeholder.
        as_int = typ == "integer"
        step = 1 if as_int else 0.1
        kw = {"label": label, "value": None, "step": step,
              "help": help_text or "Введите числовое значение", "key": widget_key,
              "placeholder": placeholder}
        if "minimum" in real:
            kw["min_value"] = int(real["minimum"]) if as_int else float(real["minimum"])
        if "maximum" in real:
            kw["max_value"] = int(real["maximum"]) if as_int else float(real["maximum"])
        return st.number_input(**kw)
    return st.text_input(label, value="", help=help_text,
                         placeholder=placeholder, key=widget_key)


def unwrap_result(raw: dict) -> dict:
    if not raw:
        return {}
    structured = raw.get("structuredContent")
    if isinstance(structured, dict):
        if len(structured) == 1 and isinstance(structured.get("result"), dict):
            return structured["result"]
        return structured
    for item in raw.get("content", []):
        if item.get("type") == "text":
            text = item.get("text", "")
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"text": text}
    return raw


def show_result(raw: dict):
    if raw.get("isError"):
        st.error("Сервер вернул ошибку инструмента (isError=true)")
    data = unwrap_result(raw)
    if not isinstance(data, dict):
        st.json(raw)
        return
    if "value" in data:
        st.metric("Результат", f"{data['value']} {data.get('unit', '')}")
        risk = data.get("risk")
        msg = data.get("interpretation", "")
        if risk == "high":
            st.error(msg)
        elif risk == "warning":
            st.warning(msg)
        elif risk == "low":
            st.success(msg)
        else:
            st.info(msg)
        if data.get("components"):
            st.subheader("Составляющие расчёта")
            st.json(data["components"])
        for warning in data.get("warnings", []):
            st.warning(warning)
        if data.get("source"):
            st.markdown(f"[Первоисточник методики]({data['source']})")
    elif isinstance(data.get("pmids"), list):
        # Public PubMed article identifiers returned by the remote MCP tool.
        # Display convenient links; keep all server fields available below.
        pmids = [str(pmid) for pmid in data["pmids"] if str(pmid).isdigit()]
        st.subheader(f"Публикации PubMed: {len(pmids)}")
        if pmids:
            st.markdown("\n".join(
                f"- [PMID {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                for pmid in pmids
            ))
        else:
            st.info("Сервер не вернул корректных идентификаторов PMID")
        with st.expander("Полный ответ внешнего инструмента"):
            st.json(data)
    elif "text" in data:
        st.write(data["text"])
    else:
        st.json(data)
    if raw.get("isError"):
        st.json(raw)


def show_packets(events: list[dict]):
    if not events:
        st.caption("Пакеты пока не получены.")
        return
    calls = [(idx, event) for idx, event in enumerate(events)
             if isinstance(event.get("packet"), dict)
             and event["packet"].get("method") == "tools/call"]
    if calls:
        index, req = calls[-1]
        req_id = req["packet"].get("id")
        corresponding = next((event for event in events[index + 1:]
                              if event.get("direction") == "server → client"
                              and isinstance(event.get("packet"), dict)
                              and event["packet"].get("id") == req_id), None)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**JSON-RPC: tools/call →**")
            st.json(req["packet"])
        with col2:
            st.markdown("**JSON-RPC: ответ ←**")
            if corresponding:
                st.json(corresponding["packet"])
            else:
                st.info("Ответ не найден в захваченных пакетах")
    st.markdown("**Полный обмен (initialize, tools/list, tools/call)**")
    for idx, event in enumerate(events, 1):
        packet = event["packet"]
        method = packet.get("method", "response") if isinstance(packet, dict) else "packet"
        with st.expander(f"{idx}. {event['direction']} — {method}"):
            st.json(packet)


@st.cache_data(ttl=45, show_spinner=False)
def list_available_tools(source: str) -> dict:
    return execute(source)


@st.cache_data(ttl=300, show_spinner=False)
def cached_remote_call(tool_name: str, canonical_args: str) -> dict:
    return execute("remote", tool_name, json.loads(canonical_args))


st.title("🩺 Clinical MCP Lab")
st.caption("Практическое задание 2 · три транспорта MCP")

with st.sidebar:
    st.header("Источник MCP")
    source = st.radio("Транспорт", list(SOURCES), format_func=SOURCES.get)
    if source == "stdio":
        st.caption("Сервер запускается клиентом как дочерний процесс; stdin/stdout — JSON-RPC.")
    elif source == "sse":
        st.caption("Локальная SSE-сессия: http://127.0.0.1:8000/sse")
    else:
        st.caption(f"Streamable HTTP: {REMOTE_URL}")
        st.caption("Внешний сервис доступен только при подключении к интернету.")
    if st.button("Обновить список инструментов"):
        list_available_tools.clear()
        st.rerun()

try:
    with st.spinner("Подключаемся по MCP и запрашиваем tools/list..."):
        response = list_available_tools(source)
    tools = response["tools"]
except Exception as exc:
    st.error(f"Не удалось подключиться к {SOURCES[source]}: {error_details(exc)}")
    if source == "sse":
        st.info("Запустите проект через python run.py либо отдельно python -m clinical_mcp.network.server")
    st.stop()

st.subheader(f"Инструменты: {len(tools)}")
if not tools:
    st.info("На выбранном MCP-сервере инструменты не найдены.")
    st.stop()

# A single searchable dropdown: it opens with the entire list and filters
# in place while the user types. No separate search input is necessary.
RUSSIAN_TOOL_NAMES = {
    "bmi": "Индекс массы тела",
    "gcs": "Шкала комы Глазго",
    "creatinine_clearance": "Клиренс креатинина",
    "list_calculators": "Список калькуляторов",
    "metabolic_bmi": "Индекс массы тела",
    "cardio_map": "Среднее артериальное давление",
    "cardio_cha2ds2_vasc": "Риск инсульта CHA₂DS₂-VASc",
    "nephro_creatinine_clearance": "Клиренс креатинина",
    "critical_gcs": "Шкала комы Глазго",
    "critical_qsofa": "Оценка qSOFA",
    "pubmed_search_articles": "Поиск статей PubMed",
}


def tool_display_name(tool: dict) -> str:
    name = tool["name"]
    title = RUSSIAN_TOOL_NAMES.get(name) or tool.get("title") or name
    return f"{title} ({name})" if title != name else name


tool_names = [tool["name"] for tool in tools]
tool_labels = {tool["name"]: tool_display_name(tool) for tool in tools}
# Newer Streamlit versions support exact substring filtering. On older
# versions, the built-in selectbox search is used without filter_mode.
picker_options = {
    "label": "Инструмент",
    "options": tool_names,
    "index": None,
    "placeholder": "Выберите инструмент или начните вводить название",
    "format_func": tool_labels.__getitem__,
    "key": f"tool-picker:{source}",
}
if "filter_mode" in inspect.signature(st.selectbox).parameters:
    picker_options["filter_mode"] = "contains"
chosen_name = st.selectbox(**picker_options)
if chosen_name is None:
    st.stop()
chosen = next(tool for tool in tools if tool["name"] == chosen_name)
st.caption(chosen.get("description", ""))

schema = chosen.get("inputSchema", {})
properties = schema.get("properties", {})
required = set(schema.get("required", []))
with st.form(key=f"clinical-form:{source}:{chosen_name}", clear_on_submit=False):
    if properties:
        st.markdown("**Параметры по JSON Schema**")
    else:
        st.caption("Инструмент не требует аргументов.")
    arguments = {}
    defaults = local_defaults(source, chosen_name)
    for name, meta in properties.items():
        if name in required:
            arguments[name] = input_widget(name, meta, True, f"{source}:{chosen_name}",
                                           default=defaults.get(name))
    optional = [(name, meta) for name, meta in properties.items() if name not in required]
    if optional:
        with st.expander(f"Дополнительные параметры ({len(optional)})", expanded=False):
            for name, meta in optional:
                arguments[name] = input_widget(name, meta, False, f"{source}:{chosen_name}",
                                               default=defaults.get(name))
    submitted = st.form_submit_button("Вызвать инструмент через MCP", type="primary")

if submitted:
    try:
        # Convert types and enforce required fields in router before the network call.
        with st.spinner("Выполняем MCP tools/call..."):
            if source == "remote":
                canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
                result = cached_remote_call(chosen_name, canonical)
            else:
                result = execute(source, chosen_name, arguments)
        st.session_state["latest_call"] = {"source": source, "tool": chosen_name, "payload": result}
    except Exception as exc:
        st.error(f"Ошибка вызова MCP: {error_details(exc)}")

latest = st.session_state.get("latest_call")
if latest and latest["source"] == source:
    st.divider()
    st.subheader(f"Результат: {latest['tool']}")
    for warning in latest["payload"].get("warnings", []):
        st.caption(f"Sanitizer: {warning}")
    if latest["payload"].get("result"):
        show_result(latest["payload"]["result"])

st.divider()
with st.expander("🔎 MCP Packet Inspector — реальные JSON-RPC пакеты", expanded=bool(latest and latest["source"] == source)):
    if latest and latest["source"] == source:
        show_packets(latest["payload"]["trace"])
    else:
        st.caption("После вызова будет показан запрос tools/call, ответ и полный протокольный обмен.")
        st.caption("Список инструментов также был запрошен по MCP: tools/list.")
