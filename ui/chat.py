"""
Data Agents — UI de Chat (Streamlit)

Interface web local que substitui o terminal para uso mais amigável.
Porta padrão: 8502

Iniciar:
    ./start.sh                                         # UI + Monitoring juntos
    streamlit run ui/chat.py --server.port 8502        # somente UI

Arquitetura da sessão:
    Usa ClaudeSDKClient persistente (igual ao run_interactive de main.py):
      - Um event loop dedicado roda em background thread via loop.run_forever()
      - O cliente é conectado uma vez e reutilizado entre mensagens
      - Histórico de conversa é mantido — respostas de aprovação funcionam corretamente
      - "Nova conversa" desconecta e reconecta o cliente (limpa histórico)
"""

import asyncio
import sys
import threading
from pathlib import Path

import streamlit as st

# ── Garante que a raiz do projeto está no path ────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Imports do projeto ────────────────────────────────────────────────────────
from commands.parser import parse_command, COMMAND_REGISTRY  # noqa: E402
from config.settings import settings  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────
MONITORING_URL = "http://localhost:8501"
CHAT_PORT = 8502
APP_TITLE = "Data Agents"
VERSION = "v2.0"

# Mapa de tool → label amigável (subconjunto representativo)
TOOL_LABELS: dict[str, str] = {
    "Agent": "🤖 Delegando para agente especialista",
    "Read": "📖 Lendo arquivo",
    "Write": "✍️  Salvando arquivo",
    "Grep": "🔍 Buscando conteúdo",
    "Glob": "📂 Listando arquivos",
    "Bash": "⚙️  Executando comando",
    "AskUserQuestion": "❓ Aguardando resposta",
    # Databricks
    "mcp__databricks__execute_sql": "🗄️  SQL no Databricks",
    "mcp__databricks__execute_sql_multi": "🗄️  SQL paralelo no Databricks",
    "mcp__databricks__list_catalogs": "📋 Unity Catalog — catálogos",
    "mcp__databricks__list_schemas": "📋 Unity Catalog — schemas",
    "mcp__databricks__list_tables": "📋 Unity Catalog — tabelas",
    "mcp__databricks__describe_table": "🔎 Inspecionando tabela",
    "mcp__databricks__get_table_stats_and_schema": "📊 Stats + schema da tabela",
    "mcp__databricks__run_job_now": "🚀 Disparando Job Databricks",
    "mcp__databricks__wait_for_run": "⏳ Aguardando conclusão do Job",
    "mcp__databricks__start_pipeline": "🚀 Iniciando Pipeline LakeFlow",
    "mcp__databricks__get_pipeline": "📡 Status do Pipeline",
    "mcp__databricks__execute_code": "⚡ Executando código serverless",
    "mcp__databricks__create_or_update_genie": "🧞 Configurando Genie Space",
    "mcp__databricks__create_or_update_dashboard": "📊 Criando AI/BI Dashboard",
    "mcp__databricks__manage_ka": "🧠 Knowledge Assistant",
    "mcp__databricks__manage_mas": "🤖 Mosaic AI Supervisor Agent",
    "mcp__databricks__query_serving_endpoint": "🔮 Consultando endpoint ML",
    # Fabric
    "mcp__fabric__list_workspaces": "📋 Workspaces do Fabric",
    "mcp__fabric_community__list_items": "📋 Itens do Fabric workspace",
    "mcp__fabric_sql__fabric_sql_execute": "🗄️  SQL no Fabric Lakehouse",
    "mcp__fabric_sql__fabric_sql_list_tables": "📋 Tabelas Fabric (todos schemas)",
    "mcp__fabric_rti__kusto_query": "🔍 Query KQL (Eventhouse)",
}

# Grupos de comandos para a sidebar
COMMAND_GROUPS: dict[str, list[str]] = {
    "📋 Intake & Planejamento": ["/brief", "/plan", "/review", "/status"],
    "⚡ Databricks": ["/sql", "/spark", "/pipeline"],
    "🏭 Microsoft Fabric": ["/fabric", "/semantic"],
    "🔍 Qualidade & Gov.": ["/quality", "/governance"],
    "🔧 Sistema": ["/health"],
    "💬 Conversacional": ["/geral"],
}

# Comandos que executam sem precisar de texto adicional
COMMANDS_NO_ARGS = {"/health", "/status", "/review"}

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ───────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }

    [data-testid="stSidebar"] { min-width: 285px !important; }

    /* Botões de comando rápido */
    .stButton > button {
        font-family: 'Courier New', monospace !important;
        font-size: 0.80em !important;
        text-align: left !important;
        padding: 4px 10px !important;
    }

    /* Separador de grupo */
    .cmd-group-label {
        font-size: 0.72em;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 8px 0 2px 0;
    }

    /* Pill de métricas */
    .metric-row { font-size: 0.75em; color: #8899aa; margin-top: 4px; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Session state ─────────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "messages": [],  # [{role, content, tools, metrics}]
        "pending_command": None,  # "/plan" | None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ── Sessão persistente com ClaudeSDKClient ────────────────────────────────────
# Equivale ao run_interactive() em main.py:
#   - Um event loop dedicado roda em background thread (loop.run_forever())
#   - ClaudeSDKClient conectado e mantido vivo entre mensagens
#   - Histórico de conversa preservado — "sim" após aprovação funciona corretamente
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⚙️ Inicializando Data Agents e MCP servers...")
def _get_agent_session() -> dict:
    """
    Cria sessão persistente:
      - loop: asyncio EventLoop rodando em daemon thread (loop.run_forever)
      - client: ClaudeSDKClient conectado — mantém histórico entre queries
      - options: ClaudeOptions mutável — thinking é ajustado por query

    Padrão idêntico ao main.py run_interactive():
        async with ClaudeSDKClient(options=options) as client:
            while True:
                await client.query(prompt)
                async for msg in client.receive_response(): ...
    """
    from agents.supervisor import build_supervisor_options
    from claude_agent_sdk import ClaudeSDKClient

    # ── 1. Event loop em background thread (run_forever) ──────────────────────
    loop = asyncio.new_event_loop()

    def _loop_thread() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    bg = threading.Thread(target=_loop_thread, daemon=True, name="data-agents-loop")
    bg.start()

    # ── 2. Opções base (thinking ajustado por query, não aqui) ────────────────
    options = build_supervisor_options(enable_thinking=False)
    options.include_partial_messages = True

    # ── 3. Cria e conecta o cliente no loop de background ─────────────────────
    client = ClaudeSDKClient(options=options)

    future = asyncio.run_coroutine_threadsafe(client.connect(), loop)
    try:
        future.result(timeout=45)
    except Exception as exc:
        raise RuntimeError(f"Falha ao conectar ClaudeSDKClient: {exc}") from exc

    return {"client": client, "options": options, "loop": loop}


def _reset_agent_session() -> None:
    """
    Desconecta e reconecta o cliente — limpa histórico de conversa.
    Equivalente ao comando 'limpar' do CLI (client.disconnect + client.connect).
    """
    try:
        session = _get_agent_session()

        async def _do_reset() -> None:
            await session["client"].disconnect()
            await session["client"].connect()

        future = asyncio.run_coroutine_threadsafe(_do_reset(), session["loop"])
        future.result(timeout=20)
    except Exception:
        pass  # Falha no reset não deve travar a UI — próxima query cria contexto novo


# ── Helpers ───────────────────────────────────────────────────────────────────
def _tool_label(name: str) -> str:
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    clean = name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()
    return f"🔧 {clean}"


def _strip_rich(text: str) -> str:
    """Remove markup Rich do texto de display dos comandos."""
    import re

    return re.sub(r"\[/?[^\]]+\]", "", text).strip()


# ── Execução do agente (ClaudeSDKClient persistente) ─────────────────────────
def _run_agent(prompt: str, enable_thinking: bool = False, session_type: str = "ui") -> dict:
    """
    Envia prompt para o ClaudeSDKClient persistente e aguarda a resposta.

    Diferença crítica em relação a query() stateless:
      - Usa client.query() + client.receive_response() (como main.py)
      - Histórico de conversa é MANTIDO entre chamadas
      - Quando o agente pede aprovação e o usuário responde "sim",
        o cliente já tem o contexto completo — PRD é lido, SPEC é gerada

    O modo thinking é ajustado em options antes de cada query:
      - /plan, /brief → enable_thinking=True  → 8000 tokens de budget
      - demais        → enable_thinking=False → thinking disabled
    """
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
    from claude_agent_sdk.types import StreamEvent

    session = _get_agent_session()
    client = session["client"]
    options = session["options"]
    loop = session["loop"]

    # Ajusta thinking antes de cada query (igual a main.py lines 462-465)
    options.thinking = (
        {"type": "enabled", "budget_tokens": 8000} if enable_thinking else {"type": "disabled"}
    )

    result: dict = {
        "text": "",
        "tools": [],
        "cost": 0.0,
        "turns": 0,
        "duration": 0.0,
        "error": None,
    }

    async def _async() -> None:
        try:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, StreamEvent):
                    ev = message.event
                    if ev.get("type") == "content_block_start":
                        blk = ev.get("content_block", {})
                        if blk.get("type") == "tool_use":
                            result["tools"].append(blk.get("name", ""))

                elif isinstance(message, AssistantMessage):
                    for blk in message.content:
                        if isinstance(blk, TextBlock) and blk.text.strip():
                            result["text"] += blk.text

                elif isinstance(message, ResultMessage):
                    result["cost"] = float(message.total_cost_usd or 0)
                    result["turns"] = int(message.num_turns or 0)
                    result["duration"] = float(message.duration_ms or 0) / 1000
                    # Persiste métricas no sessions.jsonl para o monitoramento
                    from hooks.session_logger import log_session_result

                    log_session_result(
                        message, prompt_preview=prompt[:100], session_type=session_type
                    )

        except Exception as exc:
            result["error"] = str(exc)

    # Submete a coroutine ao loop de background e aguarda conclusão
    exc_holder: list[Exception] = []

    def _submit() -> None:
        future = asyncio.run_coroutine_threadsafe(_async(), loop)
        try:
            future.result()
        except Exception as e:
            exc_holder.append(e)

    t = threading.Thread(target=_submit, daemon=True)
    t.start()
    t.join()

    if exc_holder:
        result["error"] = str(exc_holder[0])

    return result


# ── Execução direta via Haiku (sem Supervisor) ───────────────────────────────
# Bypass do Supervisor para /geral: chama claude-haiku diretamente via SDK Anthropic.
# Evita o overhead do agente orquestrador, reduzindo custo de ~$0.15 para ~$0.002.
_GERAL_MODEL = "claude-sonnet-4-6"
_GERAL_SYSTEM = (
    "Você é um assistente técnico especializado em Engenharia de Dados: "
    "Databricks, Microsoft Fabric, Apache Spark, Delta Lake, SQL, arquitetura Medallion e boas práticas. "
    "Responda em português brasileiro, de forma direta e objetiva. "
    "Use exemplos e code blocks quando enriquecer a resposta. "
    "Não peça aprovação, não crie documentos, não acesse arquivos externos."
)


def _run_geral(user_message: str) -> dict:
    """
    Chama claude-haiku diretamente via Anthropic REST API (urllib stdlib).
    Sem dependência do pacote 'anthropic' — sem passar pelo Supervisor.

    Mantém histórico de conversa em st.session_state["geral_history"] para
    suportar perguntas de follow-up dentro da mesma sessão do App.

    Custo típico: ~$0.001–0.005 por pergunta (vs ~$0.15 com Supervisor).
    """
    import json
    import time
    import urllib.request

    result: dict = {
        "text": "",
        "tools": [],
        "cost": 0.0,
        "turns": 1,
        "duration": 0.0,
        "error": None,
    }

    # Histórico de conversa para follow-ups
    if "geral_history" not in st.session_state:
        st.session_state["geral_history"] = []

    st.session_state["geral_history"].append({"role": "user", "content": user_message})

    # Mantém no máximo 20 mensagens (10 turnos) para limitar tokens de contexto
    history = st.session_state["geral_history"][-20:]

    payload = json.dumps(
        {
            "model": _GERAL_MODEL,
            "max_tokens": 2048,
            "system": _GERAL_SYSTEM,
            "messages": history,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "data-agents/1.0 (python-urllib/3)",
        },
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0

        text = data["content"][0]["text"] if data.get("content") else ""
        input_tok = data.get("usage", {}).get("input_tokens", 0)
        output_tok = data.get("usage", {}).get("output_tokens", 0)

        # Preços claude-sonnet-4-6: $3.00/1M input, $15.00/1M output
        cost = (input_tok * 3.00 + output_tok * 15.00) / 1_000_000

        result["text"] = text
        result["cost"] = cost
        result["duration"] = elapsed

        # Adiciona resposta ao histórico
        st.session_state["geral_history"].append({"role": "assistant", "content": text})

        # Grava no sessions.jsonl para o monitoramento
        from hooks.session_logger import log_session_result

        class _FakeResult:
            total_cost_usd = cost
            num_turns = 1
            duration_ms = int(elapsed * 1000)

        log_session_result(_FakeResult(), prompt_preview=user_message[:100], session_type="geral")

    except Exception as exc:
        result["error"] = str(exc)
        result["duration"] = time.time() - t0
        # Remove a mensagem do histórico em caso de erro
        if st.session_state["geral_history"]:
            st.session_state["geral_history"].pop()

    return result


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## 🤖 {APP_TITLE}")
    st.caption(f"{VERSION} · Claude Agent SDK + MCP")

    # Link para o Monitoring
    st.link_button(
        "📊 Abrir Monitoring Dashboard",
        MONITORING_URL,
        use_container_width=True,
        type="primary",
    )

    st.divider()

    # Info do sistema
    with st.expander("⚙️ Configurações", expanded=False):
        try:
            st.caption(f"**Modelo:**  `{settings.default_model}`")
            st.caption(f"**Budget:**  `${settings.max_budget_usd:.2f}`")
            st.caption(f"**Turns:**   `{settings.max_turns}`")
        except Exception:
            st.caption("_Carregue o `.env` para ver configs._")

    st.divider()

    # ── Comandos rápidos ──────────────────────────────────────────
    st.markdown("#### ⚡ Comandos Rápidos")
    st.caption("Selecione um comando para usá-lo no chat.")

    for group, cmds in COMMAND_GROUPS.items():
        st.markdown(f"<div class='cmd-group-label'>{group}</div>", unsafe_allow_html=True)
        cols = st.columns(2)
        for i, cmd in enumerate(cmds):
            key = cmd.lstrip("/")
            defn = COMMAND_REGISTRY.get(key)
            tip = defn.description if defn else cmd
            if cols[i % 2].button(
                cmd, key=f"sidebar_btn_{cmd}", help=tip, use_container_width=True
            ):
                st.session_state.pending_command = cmd
                st.rerun()

    st.divider()

    # ── Outputs gerados (por subpasta) ───────────────────────────
    st.markdown("#### 📁 Outputs Recentes")
    output_dir = ROOT / "output"

    SUBFOLDER_ICONS = {
        "prd": ("📄 PRD", "prd"),
        "specs": ("📐 SPEC", "specs"),
        "backlog": ("📋 Backlog", "backlog"),
    }

    any_files = False
    if output_dir.exists():
        for sub, (label, _) in SUBFOLDER_ICONS.items():
            sub_dir = output_dir / sub
            if sub_dir.exists():
                files = sorted(sub_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[
                    :3
                ]
                if files:
                    any_files = True
                    st.caption(f"**{label}**")
                    for f in files:
                        st.caption(f"&nbsp;&nbsp;• `{f.name}`")
    if not any_files:
        st.caption("_Nenhum arquivo gerado ainda._")

    st.divider()

    # Limpar conversa (desconecta/reconecta cliente para limpar histórico)
    if st.button("🗑️  Nova conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_command = None
        _reset_agent_session()
        st.rerun()


# ── Área principal ────────────────────────────────────────────────────────────
st.markdown("### 💬 Chat")

# Exibe histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # Ferramentas (expansível)
            tools = msg.get("tools", [])
            if tools:
                with st.expander(f"🔧 {len(tools)} ferramenta(s) executada(s)", expanded=False):
                    for t in tools:
                        st.caption(f"• {_tool_label(t)}")
            # Resposta
            st.markdown(msg["content"])
            # Métricas
            m = msg.get("metrics", {})
            if m.get("cost") or m.get("turns"):
                parts = []
                if m.get("cost"):
                    parts.append(f"💰 `${m['cost']:.4f}`")
                if m.get("turns"):
                    parts.append(f"🔄 `{m['turns']} turns`")
                if m.get("duration"):
                    parts.append(f"⏱️ `{m['duration']:.1f}s`")
                st.markdown(
                    "<div class='metric-row'>" + " &nbsp;·&nbsp; ".join(parts) + "</div>",
                    unsafe_allow_html=True,
                )


# ── Área de composição ────────────────────────────────────────────────────────
pending = st.session_state.get("pending_command")

if pending:
    # Comando selecionado via botão da sidebar
    cmd_defn = COMMAND_REGISTRY.get(pending.lstrip("/"))
    st.info(f"Comando selecionado: **`{pending}`**  —  {cmd_defn.description if cmd_defn else ''}")

    if pending in COMMANDS_NO_ARGS:
        # Executa imediatamente sem precisar de texto
        col1, col2 = st.columns([1, 5])
        if col1.button("▶  Executar", type="primary"):
            final_input = pending
            st.session_state.pending_command = None
        elif col2.button("✕ Cancelar"):
            st.session_state.pending_command = None
            st.rerun()
        else:
            st.stop()
    else:
        # Precisa de descrição da tarefa
        task_text = st.text_area(
            "Descreva a tarefa:",
            placeholder="Ex: pipeline de vendas no Databricks com Star Schema...",
            height=80,
            key="task_area",
        )
        col1, col2 = st.columns([1, 5])
        send_btn = col1.button("▶  Enviar", type="primary", disabled=not task_text.strip())
        cancel_btn = col2.button("✕ Cancelar")

        if cancel_btn:
            st.session_state.pending_command = None
            st.rerun()
        elif send_btn and task_text.strip():
            final_input = f"{pending} {task_text.strip()}"
            st.session_state.pending_command = None
        else:
            st.stop()

else:
    # Input livre via chat
    chat_input = st.chat_input(
        "Digite uma solicitação ou resposta (ex: 'sim, pode prosseguir') →",
    )
    if not chat_input:
        st.stop()
    final_input = chat_input


# ── Processamento da mensagem ─────────────────────────────────────────────────
# Adiciona mensagem do usuário ao histórico e exibe
st.session_state.messages.append({"role": "user", "content": final_input})
with st.chat_message("user"):
    st.markdown(final_input)

# Determina modo BMAD e monta prompt
command_result = parse_command(final_input)
enable_thinking = command_result is not None and command_result.bmad_mode == "full"
bmad_prompt = command_result.bmad_prompt if command_result else final_input

# Badge de modo
if command_result:
    mode_label = "🗺️ BMAD Full (planejamento)" if enable_thinking else "🚀 BMAD Express"
    agent_label = f"→ `{command_result.agent}`" if command_result.agent else ""
    st.caption(f"{mode_label} {agent_label}")

# Executa o agente
with st.chat_message("assistant"):
    tools_box = st.empty()
    text_box = st.empty()
    metric_box = st.empty()

    # session_type = nome do comando (ex: "geral", "sql") ou "ui" para texto livre
    _session_type = command_result.command.lstrip("/") if command_result else "ui"
    is_geral = command_result is not None and command_result.command == "/geral"

    if is_geral:
        # Bypass do Supervisor — chama Haiku diretamente (~$0.002 vs ~$0.15 com Supervisor)
        with st.spinner("💬 Haiku pensando..."):
            result = _run_geral(bmad_prompt)
    else:
        with st.spinner("⏳ Agente processando..."):
            result = _run_agent(
                bmad_prompt, enable_thinking=enable_thinking, session_type=_session_type
            )

    # Ferramentas usadas (apenas para Claude — Gemini não usa ferramentas)
    if result["tools"]:
        with tools_box.expander(
            f"🔧 {len(result['tools'])} ferramenta(s) executada(s)", expanded=False
        ):
            for t in result["tools"]:
                st.caption(f"• {_tool_label(t)}")

    # Resposta ou erro
    if result["error"]:
        response_text = f"❌ **Erro:** {result['error']}"
        text_box.error(response_text)
    elif result["text"]:
        response_text = result["text"]
        text_box.markdown(response_text)
    else:
        response_text = "_Agente concluiu sem resposta textual._"
        text_box.caption(response_text)

    # Métricas
    parts = []
    if result["cost"]:
        parts.append(f"💰 `${result['cost']:.4f}`")
    if result["turns"]:
        parts.append(f"🔄 `{result['turns']} turns`")
    if result["duration"]:
        parts.append(f"⏱️ `{result['duration']:.1f}s`")
    if parts:
        metric_box.markdown(
            "<div class='metric-row'>" + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True,
        )

# Salva no histórico
st.session_state.messages.append(
    {
        "role": "assistant",
        "content": response_text,
        "tools": result["tools"],
        "metrics": {
            "cost": result["cost"],
            "turns": result["turns"],
            "duration": result["duration"],
        },
    }
)

# ── FIX: força refresh da página para exibir st.chat_input novamente ──────────
# Sem st.rerun(), o Streamlit não atualiza a área de composição após o agente
# responder — o usuário ficaria sem campo de input para digitar "sim" ou continuar.
st.rerun()
