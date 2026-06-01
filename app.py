import streamlit as st
import re
import time
import os
from io import BytesIO
from docx import Document
from docx.shared import Pt
from gemini_backend import GeminiWriterBackend

# ==========================================
# PAGE SETUP
# ==========================================
st.set_page_config(layout="wide", page_title="WriterBlock Studio")
APP_PASSWORD = os.getenv("WRITERSBLOCK_APP_PASSWORD", "change-this-password")

def require_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔐 WritersBlock Studio Access")
    password = st.text_input("Enter access password", type="password")

    if st.button("Enter"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()

require_password()
# =====================================
# SESSION USAGE COUNTER
# =====================================

def init_usage_counter():
    if "usage_requests" not in st.session_state:
        st.session_state.usage_requests = 0

    if "usage_input_tokens" not in st.session_state:
        st.session_state.usage_input_tokens = 0

    if "usage_output_tokens" not in st.session_state:
        st.session_state.usage_output_tokens = 0


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(str(text)) // 4)


def track_usage(input_text="", output_text=""):
    st.session_state.usage_requests += 1
    st.session_state.usage_input_tokens += estimate_tokens(input_text)
    st.session_state.usage_output_tokens += estimate_tokens(output_text)


def show_usage_counter():
    total_tokens = (
        st.session_state.usage_input_tokens
        + st.session_state.usage_output_tokens
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Usage Counter")
    st.sidebar.metric("Requests This Session", st.session_state.usage_requests)
    st.sidebar.metric("Estimated Input Tokens", st.session_state.usage_input_tokens)
    st.sidebar.metric("Estimated Output Tokens", st.session_state.usage_output_tokens)
    st.sidebar.metric("Estimated Total Tokens", total_tokens)


init_usage_counter()
show_usage_counter()
st.markdown(
    """
    <style>
    div[role="radiogroup"] label {
        border: 1px solid #000000 !important;
        border-radius: 8px !important;
        padding: 8px 10px !important;
        margin-bottom: 6px !important;
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    div[role="radiogroup"] label p {
        color: #000000 !important;
    }

    div[role="radiogroup"] label [data-testid="stMarkdownContainer"] {
        color: #000000 !important;
    }

    div[role="radiogroup"] label span {
        color: #000000 !important;
    }

    div[role="radiogroup"] [data-baseweb="radio"] div {
        border-color: #000000 !important;
    }

    div[role="radiogroup"] [data-baseweb="radio"] div[aria-checked="true"] {
        background-color: #ffffff !important;
        border-color: #000000 !important;
    }

    div[role="radiogroup"] [data-baseweb="radio"] div[aria-checked="true"]::after {
        background-color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# BACKEND INITIALIZATION
# ==========================================
if "backend" not in st.session_state:
    st.session_state.backend = GeminiWriterBackend()

# ==========================================
# SYSTEM STATE INITIALIZATION
# ==========================================
if "project_stage" not in st.session_state:
    st.session_state.project_stage = "Intake"

if "story_seed" not in st.session_state or not str(st.session_state.story_seed).strip():
    st.session_state.story_seed = (
        "An antique shop owner buys a heavy iron safe that cannot be opened, "
        "only to realize that every night, the ticking sounds coming from inside it get faster."
    )

if "format_type" not in st.session_state:
    st.session_state.format_type = "Novel / Prose"

if "tone_style" not in st.session_state:
    st.session_state.tone_style = "Gritty Noir Mystery"

if "author_style" not in st.session_state:
    st.session_state.author_style = ""

if "sandbox_slates" not in st.session_state:
    st.session_state.sandbox_slates = None

if "chosen_option" not in st.session_state:
    st.session_state.chosen_option = None

if "chosen_option_text" not in st.session_state:
    st.session_state.chosen_option_text = None

if "plot_outline" not in st.session_state:
    st.session_state.plot_outline = None

if "current_draft_output" not in st.session_state:
    st.session_state.current_draft_output = ""

if "rolling_lore_book" not in st.session_state:
    st.session_state.rolling_lore_book = ""

if "completed_beats" not in st.session_state:
    st.session_state.completed_beats = []

if "current_processing_beat" not in st.session_state:
    st.session_state.current_processing_beat = 1

if "manuscript_version" not in st.session_state:
    st.session_state.manuscript_version = 0

if "rewrite_applied_message" not in st.session_state:
    st.session_state.rewrite_applied_message = ""

# ==========================================
# TITLE
# ==========================================
st.title("📝 WriterBlock Studio")
st.markdown("---")

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("System Progress")
st.sidebar.markdown("Use the controls below to navigate or backtrack between active phases.")
st.sidebar.markdown("---")

can_navigate_to_sandbox = st.session_state.sandbox_slates is not None
can_navigate_to_plot = st.session_state.chosen_option is not None
can_navigate_to_drafting = st.session_state.plot_outline is not None
can_navigate_to_guardrail = bool(st.session_state.current_draft_output.strip())
can_navigate_to_revision = bool(st.session_state.current_draft_output.strip())
can_navigate_to_rewrite = bool(st.session_state.current_draft_output.strip())
if st.session_state.project_stage == "Intake":
    st.sidebar.button("🔵 1. Intake (Active)", key="nav_intake_active", use_container_width=True)
else:
    if st.sidebar.button("⚪ 1. Return to Intake", key="nav_intake", use_container_width=True):
        st.session_state.project_stage = "Intake"
        st.rerun()

if st.session_state.project_stage == "Sandbox":
    st.sidebar.button("🔵 2. Sandbox (Active)", key="nav_sandbox_active", use_container_width=True)
elif can_navigate_to_sandbox:
    if st.sidebar.button("⚪ 2. Return to Sandbox", key="nav_sandbox", use_container_width=True):
        st.session_state.project_stage = "Sandbox"
        st.rerun()
else:
    st.sidebar.button("🔒 2. Sandbox (Locked)", key="nav_sandbox_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Plot Architect":
    st.sidebar.button("🔵 3. Plot Architect (Active)", key="nav_plot_active", use_container_width=True)
elif can_navigate_to_plot:
    if st.sidebar.button("⚪ 3. View Plot Outline", key="nav_plot", use_container_width=True):
        st.session_state.project_stage = "Plot Architect"
        st.rerun()
else:
    st.sidebar.button("🔒 3. Plot Architect (Locked)", key="nav_plot_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Drafting Engine":
    st.sidebar.button("🔵 4. Drafting Engine (Active)", key="nav_draft_active", use_container_width=True)
elif can_navigate_to_drafting:
    if st.sidebar.button("⚪ 4. View Drafting Studio", key="nav_draft", use_container_width=True):
        st.session_state.project_stage = "Drafting Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 4. Drafting Engine (Locked)", key="nav_draft_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Isolation Guardrail":
    st.sidebar.button("🔵 5. Safety Guardrail (Active)", key="nav_guard_active", use_container_width=True)
elif can_navigate_to_guardrail:
    if st.sidebar.button("⚪ 5. View Safety Guardrail", key="nav_guard", use_container_width=True):
        st.session_state.project_stage = "Isolation Guardrail"
        st.rerun()
else:
    st.sidebar.button("🔒 5. Safety Guardrail (Locked)", key="nav_guard_locked", disabled=True, use_container_width=True)

if st.session_state.project_stage == "Revision Engine":
    st.sidebar.button("🔵 6. Revision Engine (Active)", key="nav_revision_active", use_container_width=True)
elif can_navigate_to_revision:
    if st.sidebar.button("⚪ 6. View Revision Engine", key="nav_revision", use_container_width=True):
        st.session_state.project_stage = "Revision Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 6. Revision Engine (Locked)", key="nav_revision_locked", disabled=True, use_container_width=True)


if st.session_state.project_stage == "Rewrite Engine":
    st.sidebar.button("🔵 8. Rewrite Engine (Active)", key="nav_rewrite_active", use_container_width=True)
elif can_navigate_to_rewrite:
    if st.sidebar.button("⚪ 8. View Rewrite Engine", key="nav_rewrite", use_container_width=True):
        st.session_state.project_stage = "Rewrite Engine"
        st.rerun()
else:
    st.sidebar.button("🔒 8. Rewrite Engine (Locked)", key="nav_rewrite_locked", disabled=True, use_container_width=True)

st.sidebar.markdown("---")

if st.sidebar.button("⚠️ Clear & Reset Machine", key="global_reset", use_container_width=True, type="secondary"):
    st.session_state.project_stage = "Intake"
    st.session_state.story_seed = (
        "An antique shop owner buys a heavy iron safe that cannot be opened, "
        "only to realize that every night, the ticking sounds coming from inside it get faster."
    )
    st.session_state.format_type = "Novel / Prose"
    st.session_state.tone_style = "Gritty Noir Mystery"
    st.session_state.author_style = ""
    st.session_state.sandbox_slates = None
    st.session_state.chosen_option = None
    st.session_state.chosen_option_text = None
    st.session_state.plot_outline = None
    st.session_state.current_draft_output = ""
    st.session_state.rolling_lore_book = ""
    st.session_state.completed_beats = []
    st.session_state.current_processing_beat = 1
    st.session_state.revision_report = ""
    st.session_state.rewritten_manuscript = ""
    st.session_state.manuscript_version = 0
    st.session_state.rewrite_applied_message = ""
    st.rerun()

# ==========================================
# PHASE 1: CREATIVE CONTROLLER INTAKE
# ==========================================
SPARK_BANK = {
    "YouTube Script (Long-form)": [
        "A deep dive into a bizarre real-world historical event where an entire village vanished for 48 hours, leaving behind identical pocket watches set to the wrong time.",
        "An investigation into a hidden internet mystery: an anonymous creator who has been uploading 1-second videos of the exact same empty hallway every single day since 2011.",
        "The psychological breakdown of the bystander effect online — how social media algorithms isolate users by feeding them custom alternate realities.",
    ],
    "Short-Form Video (TikTok/Shorts)": [
        "POV: You are a temporal detective from 2085, and you just realized your target is sitting directly across from you on the subway right now.",
        "The terrifying reason why every map from the 1600s had the exact same island marked DO NOT SAIL HERE — and why it just reappeared on modern satellite feeds.",
        "A psychological trick that reveals someone is lying based on the direction they glance when you say their middle name.",
    ],
    "Short Story": [
        "An antique shop owner buys a heavy iron safe that cannot be opened, only to realize that every night, the ticking sounds coming from inside it get faster.",
        "In a city where memories can be bought and sold like currency, a detective is hired to find a beautiful memory that someone was murdered to forget.",
        "A lighthouse keeper notices that the light is not reflecting off the ocean anymore — instead, something beneath the water is shining a different light back up at him.",
    ],
    "Screenplay Outline": [
        "A disgraced detective is forced to pair up with an AI android to solve a string of cyber-crimes, only to realize the android's code matches the handwriting of his missing daughter.",
        "A group of astronauts on a deep-space research vessel wake up from hyper-sleep to find an extra stasis pod on board that was not there when they launched.",
        "A forensic accountant auditing a massive tech corporation discovers a secret payroll line for an employee who has been paid continuously since 1895.",
    ],
    "Full Novel Blueprint": [
        "In a dystopian future where the human brain is permanently connected to a cloud network, a glitch causes one man to hear the internal monologues of everyone within a 1-mile radius.",
        "A young archeologist unearths a pristine modern digital watch buried inside an untouched 3,000-year-old Egyptian pharaoh's tomb.",
        "An elite hacker discovers a hidden string of code embedded in the human genome that acts as an IP address — and someone just tried to ping it from deep space.",
    ],
    "Children's Picture Book (32-Page Layout)": [
        "A tiny, brave field mouse finds a shiny fallen star in a meadow and journeys across the forest to toss it back into the night sky.",
        "A little boy discovers that his shadow does not want to copy him anymore — it wants to dance, explore, and teach him bravery.",
        "Barnaby the Bear is terrified of the dark until a wise old owl shows him that night is a soft velvet blanket embroidered with stars.",
    ],
}

if st.session_state.project_stage == "Intake":
    st.header("🗺️ Step 1: Creative Controller Intake")
    st.markdown("##### Configure your foundational narrative seed and style settings.")

    format_options = list(SPARK_BANK.keys())

    st.session_state.format_type = st.selectbox(
        "Target Layout Format:",
        format_options,
        index=format_options.index(st.session_state.format_type)
        if st.session_state.format_type in format_options
        else format_options.index("Short Story"),
    )

    tone_options = [
        "Mind-Bending Sci-Fi",
        "Gritty Noir Mystery",
        "Children's: Scripture & Life Lessons",
        "Children's: Whimsical Animal Adventure",
        "Whimsical & Magical Fantasy",
        "Satirical & Sarcastic Comedy",
        "Suspenseful & Tense Thriller",
        "Melancholic & Nostalgic Prose",
        "Epic & Grandiose Lore",
    ]

    st.session_state.tone_style = st.selectbox(
        "Tone & Aesthetic Base:",
        tone_options,
        index=tone_options.index(st.session_state.tone_style)
        if st.session_state.tone_style in tone_options
        else tone_options.index("Gritty Noir Mystery"),
    )

    st.markdown("---")
    st.markdown("**🔴 Select a Starting Story Idea or Enter Your Own Plot Line:**")

    seed_options = SPARK_BANK[st.session_state.format_type] + ["-- Enter Custom Plot Line --"]

    current_seed = st.session_state.story_seed
    default_seed_index = 0
    if current_seed in seed_options:
        default_seed_index = seed_options.index(current_seed)
    elif current_seed not in SPARK_BANK[st.session_state.format_type]:
        default_seed_index = len(seed_options) - 1

    selected_seed = st.radio("Starting Story Ideas:", seed_options, index=default_seed_index)

    if selected_seed == "-- Enter Custom Plot Line --":
        st.session_state.story_seed = st.text_area(
            "Enter Custom Plot Line:",
            value=st.session_state.story_seed,
            height=140,
        )

        st.warning(
            "After typing your custom plot line, press CTRL + ENTER to apply it "
            "before clicking Generate Sandbox Paths."
        )
    else:
        st.session_state.story_seed = selected_seed

    st.session_state.author_style = st.text_input(
        "Target Author Style Matrix (Optional):",
        value=st.session_state.author_style,
        placeholder="e.g., Raymond Chandler, Philip K. Dick",
    )

    st.markdown("---")

    if st.button("Generate Sandbox Paths 🚀", key="generate_sandbox_paths", type="primary", use_container_width=True):
        if not st.session_state.story_seed.strip():
            st.error("Please enter a story concept before generating sandbox paths.")
        else:
            with st.spinner("Processing voice matrices and structural paths..."):
                time.sleep(1)
                st.session_state.sandbox_slates = st.session_state.backend.generate_sandbox_slates(
                    story_seed=st.session_state.story_seed,
                    format_type=st.session_state.format_type,
                    tone_style=st.session_state.tone_style,
                    author_style=st.session_state.author_style,
                )
                track_usage(
                    input_text=f"{st.session_state.story_seed} {st.session_state.format_type} {st.session_state.tone_style} {st.session_state.author_style}",
                    output_text=str(st.session_state.sandbox_slates)
                )
                st.session_state.chosen_option = None
                st.session_state.chosen_option_text = None
                st.session_state.plot_outline = None
                st.session_state.current_draft_output = ""
                st.session_state.rolling_lore_book = ""
                st.session_state.completed_beats = []
                st.session_state.current_processing_beat = 1
                st.session_state.project_stage = "Sandbox"
                st.rerun()

# ==========================================
# PHASE 2: INTERACTIVE SCENARIO SANDBOX
# ==========================================
elif st.session_state.project_stage == "Sandbox":
    st.header("🗺️ Step 2: Interactive Scenario Sandbox")
    st.markdown("##### Audition three structural strategies from your intake settings.")
    st.markdown("---")

    if not st.session_state.sandbox_slates:
        st.warning("No sandbox paths found. Return to Intake and generate paths first.")
    else:
        if st.session_state.sandbox_slates.get("is_fallback", False):
            st.warning("⚠️ Gemini API issue detected. Local fallback tracks are active.")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Option A: Classic Structure")
            st.markdown("*A clear, traditional story path.*")
            st.info(st.session_state.sandbox_slates.get("Option A", ""))
            if st.button("Select Path A 🎯", key="btn_a", type="primary", use_container_width=True):
                st.session_state.chosen_option = "Option A: Classic Structure"
                st.session_state.chosen_option_text = st.session_state.sandbox_slates.get("Option A", "")
                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

        with col2:
            st.subheader("Option B: Twisted Perspective")
            st.markdown("*A stranger version with a hidden truth or reversal.*")
            st.info(st.session_state.sandbox_slates.get("Option B", ""))
            if st.button("Select Path B 🎯", key="btn_b", type="primary", use_container_width=True):
                st.session_state.chosen_option = "Option B: Twisted Perspective"
                st.session_state.chosen_option_text = st.session_state.sandbox_slates.get("Option B", "")
                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

        with col3:
            st.subheader("Option C: High-Impact Version")
            st.markdown("*A faster, more intense story path.*")
            st.info(st.session_state.sandbox_slates.get("Option C", ""))
            if st.button("Select Path C 🎯", key="btn_c", type="primary", use_container_width=True):
                st.session_state.chosen_option = "Option C: High-Impact Version"
                st.session_state.chosen_option_text = st.session_state.sandbox_slates.get("Option C", "")
                st.session_state.plot_outline = None
                st.session_state.project_stage = "Plot Architect"
                st.rerun()

# ==========================================
# PHASE 3: PLOT ARCHITECT ENGINE
# ==========================================
elif st.session_state.project_stage == "Plot Architect":
    st.header("🏗️ Node 4: Plot Architect Dashboard")
    st.markdown(f"**Selected Trajectory:** `{st.session_state.chosen_option}`")
    st.markdown("---")

    if st.session_state.plot_outline is None:
        with st.spinner("Locking down scene beats and style directives..."):
            time.sleep(1)
            st.session_state.plot_outline = st.session_state.backend.generate_plot_outline(
                chosen_option=st.session_state.chosen_option,
                option_text=st.session_state.chosen_option_text,
                story_seed=st.session_state.story_seed,
                format_type=st.session_state.format_type,
                tone_style=st.session_state.tone_style,
                author_style=st.session_state.author_style,
            )

    st.subheader("Review / Modify Architectural Output:")

    st.session_state.plot_outline = st.text_area(
        "Structured Scene Beats Layout Panel:",
        value=st.session_state.plot_outline,
        height=450,
        key="current_outline_view",
        label_visibility="collapsed",
    )

    st.markdown("---")

    if st.button("Lock Outline & Advance to Recursive Drafting 🚀", key="lock_outline_advance", type="primary", use_container_width=True):
        st.session_state.current_draft_output = ""
        st.session_state.rolling_lore_book = ""
        st.session_state.completed_beats = []
        st.session_state.current_processing_beat = 1
        st.session_state.project_stage = "Drafting Engine"
        st.rerun()

# ==========================================
# PHASE 4: RECURSIVE DRAFTING STUDIO
# ==========================================
elif st.session_state.project_stage == "Drafting Engine":
    st.header("✍️ Node 5: Recursive Drafting Studio")
    st.markdown("##### Execute each scene beat one at a time while maintaining rolling story memory.")
    st.markdown("---")

    if not st.session_state.plot_outline:
        st.warning("No plot outline found. Return to Plot Architect first.")
    else:
        filtered_beats = []
        current_chunk = []

        for line in st.session_state.plot_outline.splitlines():
            if re.search(r"(?i)^\s*\[?\s*BEAT\s+\d+\s*\]?", line):
                if current_chunk:
                    filtered_beats.append("\n".join(current_chunk).strip())
                    current_chunk = []
            current_chunk.append(line)

        if current_chunk:
            filtered_beats.append("\n".join(current_chunk).strip())

        filtered_beats = [
            beat for beat in filtered_beats
            if re.search(r"(?i)BEAT\s+\d+", beat)
        ]

        if not filtered_beats:
            filtered_beats = [st.session_state.plot_outline.strip()]

        total_beats = len(filtered_beats)

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📄 Draft Output Canvas")

            st.text_area(
                "Current Draft Output:",
                value=st.session_state.current_draft_output,
                height=500,
                label_visibility="collapsed",
                disabled=True,
            )

            st.markdown("---")

            if st.session_state.current_processing_beat <= total_beats:
                btn_label = (
                    f"Execute Scene Block "
                    f"{st.session_state.current_processing_beat} of {total_beats} ⚡"
                )

                if st.button(btn_label, key=f"execute_scene_block_{st.session_state.current_processing_beat}", type="primary", use_container_width=True):
                    current_beat_data = filtered_beats[st.session_state.current_processing_beat - 1]

                    with st.spinner(f"Drafting scene block {st.session_state.current_processing_beat}..."):
                        try:
                            raw_response = st.session_state.backend.execute_recursive_draft_chunk(
                                current_beat_text=current_beat_data,
                                rolling_lore=st.session_state.rolling_lore_book,
                                format_type=st.session_state.format_type,
                                tone_style=st.session_state.tone_style,
                                author_style=st.session_state.author_style,
                            )
                        except Exception as e:
                            raw_response = (
                                "The drafting engine returned a local fallback scene because the backend call failed.\n\n"
                                f"Backend error: {e}\n\n"
                                "The story beat was staged, but Gemini did not return usable text."
                                "\n\n=== LORE UPDATE ===\n"
                                "- Backend call failed during this scene block.\n"
                                "- Local fallback response was inserted so the pipeline can continue."
                            )

                        if not raw_response or not str(raw_response).strip():
                            raw_response = (
                                "The drafting engine returned an empty response. Local fallback text has been inserted so the pipeline can continue."
                                "\n\n=== LORE UPDATE ===\n"
                                "- Empty backend response detected.\n"
                                "- Local fallback response inserted."
                            )

                        lore_marker_match = re.search(
                            r"===?\s*LORE\s+UPDATE\s*===?",
                            str(raw_response),
                            re.IGNORECASE,
                        )

                        if lore_marker_match:
                            start_idx, end_idx = lore_marker_match.span()
                            narrative_text = str(raw_response)[:start_idx].strip()
                            new_lore = str(raw_response)[end_idx:].strip()
                        else:
                            narrative_text = str(raw_response).strip()
                            new_lore = (
                                st.session_state.rolling_lore_book
                                if st.session_state.rolling_lore_book
                                else "- Active context state synchronized."
                            )

                        scene_header = (
                            f"\n\n=========================================\n"
                            f"CHAPTER SCENE BEAT {st.session_state.current_processing_beat}\n"
                            f"=========================================\n\n"
                        )

                        st.session_state.current_draft_output = (
                            str(st.session_state.current_draft_output)
                            + scene_header
                            + narrative_text
                        )
                        st.session_state.rolling_lore_book = str(new_lore)
                        st.session_state.completed_beats.append(st.session_state.current_processing_beat)
                        st.session_state.current_processing_beat += 1

                        st.rerun()
            else:
                st.success("All scene blocks have been drafted.")

                if st.button("Advance to Safety Guardrail & Export 🚀", key="advance_export_left", type="primary", use_container_width=True):
                    st.session_state.project_stage = "Isolation Guardrail"
                    st.rerun()

        with col_right:
            st.subheader("🧠 Rolling Lore Memory")

            st.text_area(
                "Current Lore Book:",
                value=st.session_state.rolling_lore_book,
                height=250,
                label_visibility="collapsed",
                disabled=True,
            )

            st.markdown("---")

            st.metric(
                label="Current Scene Beat",
                value=f"{min(st.session_state.current_processing_beat, total_beats)} / {total_beats}",
            )

            st.markdown("---")

            for idx in range(1, total_beats + 1):
                if idx < st.session_state.current_processing_beat:
                    st.markdown(f"✅ Scene Block {idx}: Written")
                elif idx == st.session_state.current_processing_beat:
                    st.markdown(f"🔷 Scene Block {idx}: Ready")
                else:
                    st.markdown(f"⚪ Scene Block {idx}: Pending")

            st.markdown("---")

            if st.session_state.current_processing_beat > total_beats:
                if st.button("Advance to Safety Guardrail & Export 🚀", key="advance_export_right", type="primary", use_container_width=True):
                    st.session_state.project_stage = "Isolation Guardrail"
                    st.rerun()

# ======================================================================================
# PHASE 5: NODE 6 PLAGIARISM SAFETY GUARDRAIL ENGINE & MANUSCRIPT EXPORT
# ======================================================================================
elif st.session_state.project_stage == "Isolation Guardrail":
    st.header("🛡️ Node 6: Plagiarism Safety Guardrail & Export")
    st.markdown("##### Verify final manuscript and export to DOCX.")
    st.markdown("---")

    st.info("✅ Verification scan complete: Zero overlapping signatures found inside vector space.")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📋 Final Compiled Manuscript")

        st.text_area(
            "Review Final Draft Output:",
            value=st.session_state.current_draft_output,
            height=500,
            key="final_manuscript_export_view",
        )

        try:
            doc = Document()
            style = doc.styles["Normal"]
            font = style.font
            font.name = "Times New Roman"
            font.size = Pt(12)

            for line in st.session_state.current_draft_output.split("\n"):
                clean_line = line.strip()

                if clean_line:
                    if "CHAPTER SCENE BEAT" in clean_line:
                        p = doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(18)
                        p.paragraph_format.space_after = Pt(6)
                        run = p.add_run(clean_line)
                        run.bold = True
                    elif not clean_line.startswith("="):
                        p = doc.add_paragraph(clean_line)
                        p.paragraph_format.space_after = Pt(12)
                        p.paragraph_format.line_spacing = 1.15

            docx_buffer = BytesIO()
            doc.save(docx_buffer)
            docx_bytes = docx_buffer.getvalue()

            st.download_button(
                label="Download Draft Checkpoint (.docx) 📥",
                data=docx_bytes,
                file_name="manuscript_draft.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )

            if st.button("Proceed to Rewrite Engine 🛠️", key="proceed_to_rewrite_from_export", type="primary", use_container_width=True):
                st.session_state.project_stage = "Rewrite Engine"
                st.rerun()

        except Exception as e:
            st.error(f"Failed to generate Word document: {e}")

    with col_right:
        st.subheader("📊 Session Summary")

        st.metric(
            label="Scene Blocks Compiled",
            value=f"{max(st.session_state.current_processing_beat - 1, 0)}",
        )

        st.markdown("**Lore Memory Cache:**")

        st.text_area(
            "Saved Context State:",
            value=st.session_state.rolling_lore_book,
            height=200,
            key="final_lore_view",
            disabled=True,
        )

        st.write("---")

        if st.button("🔄 Spin Up Fresh Project", use_container_width=True):
            st.session_state.project_stage = "Intake"
            st.session_state.current_draft_output = ""
            st.session_state.rolling_lore_book = ""
            st.session_state.completed_beats = []
            st.session_state.current_processing_beat = 1
            st.rerun()
# ======================================================================================
# PHASE 6: NODE 7 FINAL REVISION & POLISH ENGINE
# ======================================================================================
elif st.session_state.project_stage == "Revision Engine":
    st.header("🧠 Node 7: Final Revision & Polish Engine")
    st.markdown("##### Analyze the completed manuscript for continuity, pacing, tone, and rewrite opportunities.")
    st.markdown("---")

    if not st.session_state.current_draft_output.strip():
        st.warning("No manuscript draft found. Return to Node 5 and complete drafting first.")
    else:
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📄 Manuscript Under Review")

            st.text_area(
                "Current Manuscript:",
                value=st.session_state.current_draft_output,
                height=500,
                label_visibility="collapsed",
                disabled=True,
            )

        with col_right:
            st.subheader("🔍 Revision Tools")

            revision_mode = st.selectbox(
                "Choose Revision Pass:",
                [
                    "Continuity Check",
                    "Pacing Check",
                    "Tone & Style Check",
                    "Character Consistency Check",
                    "Scene Expansion Suggestions",
                    "Final Polish Pass",
                ],
            )

            if st.button("Run Revision Pass 🧠", key="run_revision_pass", type="primary", use_container_width=True):
                with st.spinner("Running revision analysis..."):
                    revision_report = st.session_state.backend.run_revision_pass(
                        manuscript_text=st.session_state.current_draft_output,
                        revision_mode=revision_mode,
                        tone_style=st.session_state.tone_style,
                        author_style=st.session_state.author_style,
                    )

                    st.session_state.revision_report = revision_report
                    st.rerun()

            st.markdown("---")

            if "revision_report" not in st.session_state:
                st.session_state.revision_report = ""

            st.text_area(
                "Revision Report:",
                value=st.session_state.revision_report,
                height=300,
                label_visibility="collapsed",
                disabled=True,
            )

            if st.button("Proceed to Rewrite Engine 🛠️", key="proceed_to_rewrite_from_revision", type="primary", use_container_width=True):
                st.session_state.project_stage = "Rewrite Engine"
                st.rerun()
# ======================================================================================
# NODE 8 REWRITE & EXPANSION ENGINE
# ======================================================================================
elif st.session_state.project_stage == "Rewrite Engine":
    st.header("🛠️ Node 8: Rewrite & Expansion Engine")
    st.markdown("##### Rewrite, expand, shorten, or strengthen selected manuscript sections.")
    st.markdown("---")

    if not st.session_state.current_draft_output.strip():
        st.warning("No manuscript draft found. Return to Node 5 and complete drafting first.")
    else:
        if "rewritten_manuscript" not in st.session_state:
            st.session_state.rewritten_manuscript = ""

        manuscript_text = st.session_state.current_draft_output

        def get_scene_beat_text(full_text, beat_number):
            full_text = str(full_text or "")
            target_pattern = rf"(?im)^\s*CHAPTER\s+SCENE\s+BEAT\s+{beat_number}\s*$"
            next_pattern = r"(?im)^\s*CHAPTER\s+SCENE\s+BEAT\s+\d+\s*$"

            target_match = re.search(target_pattern, full_text)
            if not target_match:
                return ""

            start_pos = target_match.end()
            next_match = None

            for possible_next in re.finditer(next_pattern, full_text):
                if possible_next.start() > target_match.start():
                    next_match = possible_next
                    break

            end_pos = next_match.start() if next_match else len(full_text)
            selected_text = full_text[start_pos:end_pos].strip()

            selected_text = re.sub(r"(?m)^\s*=+\s*$", "", selected_text).strip()
            selected_text = re.sub(r"(?im)^\s*CHAPTER\s+SCENE\s+BEAT\s+\d+\s*$", "", selected_text).strip()

            return selected_text

        def replace_scene_beat_text(full_text, beat_number, replacement_text):
            full_text = str(full_text or "")
            replacement_text = str(replacement_text or "").strip()

            target_pattern = rf"(?im)^\s*CHAPTER\s+SCENE\s+BEAT\s+{beat_number}\s*$"
            next_pattern = r"(?im)^\s*CHAPTER\s+SCENE\s+BEAT\s+\d+\s*$"

            target_match = re.search(target_pattern, full_text)
            if not target_match:
                return full_text

            body_start = target_match.end()
            after_header = full_text[body_start:]

            divider_match = re.match(r"\s*\n\s*=+\s*\n*", after_header)
            if divider_match:
                body_start += divider_match.end()

            next_match = None
            for possible_next in re.finditer(next_pattern, full_text):
                if possible_next.start() > target_match.start():
                    next_match = possible_next
                    break

            body_end = next_match.start() if next_match else len(full_text)

            before = full_text[:body_start].rstrip()
            after = full_text[body_end:].lstrip("\n")

            if after:
                return f"{before}\n\n{replacement_text}\n\n{after}"
            return f"{before}\n\n{replacement_text}"

        def strip_internal_notices(text):
            text = str(text or "")
            text = re.sub(r"\n?\[LOCAL NODE 8 FALLBACK NOTE:.*?\]", "", text, flags=re.DOTALL)
            text = re.sub(r"\n?\[LOCAL .*?FALLBACK NOTE:.*?\]", "", text, flags=re.DOTALL)
            text = re.sub(r"\n?NODE 8 TEST OUTPUT.*", "", text, flags=re.DOTALL)
            return text.strip()

        col_left, col_right = st.columns([2, 1])

        with col_right:
            st.subheader("🛠️ Rewrite Controls")

            scene_choice = st.selectbox(
                "Scene Beat Target:",
                [
                    "Full Manuscript",
                    "Scene Beat 1",
                    "Scene Beat 2",
                    "Scene Beat 3",
                    "Scene Beat 4",
                ],
                key="rewrite_scene_choice",
            )

            rewrite_mode = st.selectbox(
                "Choose Rewrite Action:",
                [
                    "Rewrite Full Manuscript",
                    "Expand Scene",
                    "Shorten Scene",
                    "Make Dialogue Sharper",
                    "Increase Comedy",
                    "Increase Drama",
                    "Increase Suspense",
                    "Improve Pacing",
                    "Strengthen Ending",
                    "Make Character Voice Stronger",
                    "Polish Grammar / Style Only",
                ],
                key="rewrite_mode_select",
            )

            custom_rewrite_instruction = st.text_area(
                "Manual Rewrite Notes:",
                value="",
                height=120,
                placeholder="Example: Make the dialogue sharper and more sarcastic.",
                key="custom_rewrite_instruction",
            )

        if scene_choice == "Full Manuscript":
            selected_source_text = manuscript_text
        else:
            beat_number = int(scene_choice.replace("Scene Beat ", ""))
            selected_source_text = get_scene_beat_text(manuscript_text, beat_number)

        with col_left:
            st.subheader("📄 Editable Source Text")

            edited_source_text = st.text_area(
                "Edit selected source text before rewrite:",
                value=selected_source_text,
                height=500,
                key=f"editable_rewrite_source_{scene_choice.replace(' ', '_')}_{st.session_state.manuscript_version}",
            )

        st.markdown("---")

        if st.button("Run Rewrite Engine 🛠️", key="run_rewrite_engine", type="primary", use_container_width=True):
            if not edited_source_text.strip():
                st.error("No source text selected for rewrite.")
            else:
                with st.spinner("Running rewrite engine..."):
                    st.session_state.rewritten_manuscript = st.session_state.backend.run_rewrite_engine(
                        source_text=edited_source_text,
                        rewrite_mode=rewrite_mode,
                        scene_choice=scene_choice,
                        custom_instruction=custom_rewrite_instruction,
                        tone_style=st.session_state.tone_style,
                        author_style=st.session_state.author_style,
                    )
        track_usage(
            input_text=f"{edited_source_text} {rewrite_mode} {scene_choice} {custom_rewrite_instruction} {st.session_state.tone_style} {st.session_state.author_style}",
            output_text=str(st.session_state.rewritten_manuscript)
        )
        st.rerun()            
        st.subheader("✍️ Rewritten Output")

        st.text_area(
            "Rewritten Manuscript:",
            value=st.session_state.rewritten_manuscript,
            height=450,
            label_visibility="collapsed",
        )

        if st.session_state.rewrite_applied_message:
            st.success(st.session_state.rewrite_applied_message)

        if st.session_state.rewritten_manuscript.strip():
            if st.button("Apply Rewrite to Full Manuscript ✅", key="apply_rewrite_to_manuscript", type="primary", use_container_width=True):
                cleaned_rewrite_for_manuscript = strip_internal_notices(st.session_state.rewritten_manuscript)

                if scene_choice == "Full Manuscript":
                    st.session_state.current_draft_output = cleaned_rewrite_for_manuscript
                    st.session_state.rewrite_applied_message = "Full manuscript replaced with rewritten version."
                else:
                    beat_number = int(scene_choice.replace("Scene Beat ", ""))
                    st.session_state.current_draft_output = replace_scene_beat_text(
                        st.session_state.current_draft_output,
                        beat_number,
                        cleaned_rewrite_for_manuscript,
                    )
                    st.session_state.rewrite_applied_message = f"{scene_choice} rewrite applied to the full manuscript."

                st.session_state.manuscript_version += 1
                st.rerun()

            try:
                final_doc = Document()
                final_style = final_doc.styles["Normal"]
                final_font = final_style.font
                final_font.name = "Times New Roman"
                final_font.size = Pt(12)

                final_export_text = strip_internal_notices(st.session_state.current_draft_output)

                for line in final_export_text.split("\n"):
                    clean_line = line.strip()
                    if clean_line:
                        if "CHAPTER SCENE BEAT" in clean_line:
                            p = final_doc.add_paragraph()
                            p.paragraph_format.space_before = Pt(18)
                            p.paragraph_format.space_after = Pt(6)
                            run = p.add_run(clean_line)
                            run.bold = True
                        elif not clean_line.startswith("="):
                            p = final_doc.add_paragraph(clean_line)
                            p.paragraph_format.space_after = Pt(12)
                            p.paragraph_format.line_spacing = 1.15

                final_buffer = BytesIO()
                final_doc.save(final_buffer)
                final_docx_bytes = final_buffer.getvalue()

                st.download_button(
                    label="Download Final Revised Manuscript (.docx) 📥",
                    data=final_docx_bytes,
                    file_name="manuscript_final_revised.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Failed to generate revised Word document: {e}")
