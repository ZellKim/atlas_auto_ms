# CDM Publishing Strategy Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a verified 23-slide, 40-minute v8 presentation that helps CDM-novice clinicians turn one clinical topic into a research type and a feasibility-review submission, while limiting the AI section to a short automation demonstration.

**Architecture:** Preserve the existing v6/v7 decks and add an independent, data-driven v8 builder that reuses their stable PowerPoint helpers. Keep the static deck reproducible without the external video, then use a separate Windows PowerPoint COM postprocessor to embed the edited MP4 and another COM utility to export slide previews for visual QA. Store the canonical speaker script in tracked documentation and copy it beside the generated deck for delivery.

**Tech Stack:** Python 3.13, python-pptx 1.0.2, Pillow 12.2, pywin32 312, Microsoft PowerPoint COM, pytest, local CDM publication CSV files.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-13-cdm-publishing-strategy-presentation-design.md` as the approved content contract.
- Preserve the exact title `Publishing Strategy for OMOP CDM-Based Clinical Research` and subtitle `Clinical Question Design, Evidence Packaging, and AI-Assisted Automation`.
- Preserve the core message in the opening and closing: `CDM 연구는 데이터베이스를 설명하는 데서 시작하지 않습니다. 임상질문의 동사를 고르고, 필요한 데이터와 환자 수를 확인하는 데서 시작합니다.`
- Preserve the existing v6 and v7 output files; v8 must write to new filenames.
- Use only examples verified in the local publication CSV. `validate_examples()` must fail fast if a cited example disappears.
- Keep the deck at exactly 23 slides and the scripted delivery at 37–38 minutes, leaving about 2 minutes of transition buffer within the 40-minute session.
- Keep the AI section to one 45–60 second edited demonstration on slide 20: cohort definition → Generate → completed status → result/patient-count collection.
- Do not present AI as replacing clinical judgment, study design, or feasibility decisions.
- Build a usable static slide 20 even when the MP4 is absent. Video embedding is a separate, explicit postprocessing step.
- Generated `.pptx`, `.png`, and copied delivery `.md` files under `CDM발표/` remain ignored build artifacts. Source, tests, and canonical documentation are tracked.
- Do not use credentials or network calls in the presentation build.
- Before every commit, verify the changed files and avoid including unrelated user work.

## File Map

### Files to modify

- `pyproject.toml` — add an optional `presentation` dependency group.
- `data/scripts/build_cdm_research_activation_ppt.py` — bring the existing v6 helper/builder into version control without changing its output contract.
- `data/scripts/build_cdm_activation_ppt_v7.py` — bring the existing v7 extension into version control without changing its 29-slide output contract.

### Files to create

- `data/scripts/build_cdm_publishing_strategy_ppt_v8.py` — canonical 23-slide v8 builder.
- `data/scripts/embed_ppt_video.py` — embed the edited MP4 into slide 20 using PowerPoint COM.
- `data/scripts/render_ppt_preview.py` — export every slide as PNG using PowerPoint COM.
- `tests/test_cdm_publishing_strategy_ppt_v8.py` — structural, content, timing, and asset tests.
- `tests/test_ppt_video_tools.py` — path validation and non-COM helper tests for postprocessing tools.
- `docs/presentations/cdm_speaker_script_v8_260713.md` — canonical 23-section Korean speaker script.

### Generated delivery artifacts

- `CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713.pptx`
- `CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713_with_video.pptx`
- `CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713_preview/`
- `CDM발표/cdm_speaker_script_v8_260713.md`
- Expected input video: `CDM발표/ai_cohort_generate_demo_260713.mp4`

## Slide Contract

| # | Slide title | Act | Script seconds |
|---:|---|---|---:|
| 1 | Publishing Strategy for OMOP CDM-Based Clinical Research | 1 | 30 |
| 2 | 그기 논문이 됩니까? | 1 | 90 |
| 3 | 오늘 답할 두 가지 | 1 | 60 |
| 4 | CDM as Research Infrastructure | 2 | 100 |
| 5 | Distributed Research Network | 2 | 120 |
| 6 | Four Question Verbs | 3 | 90 |
| 7 | From Clinical Question to Study Type | 3 | 90 |
| 8 | What Has Been Published | 3 | 120 |
| 9 | Describe: 어떤 질문인가? | 4 | 120 |
| 10 | Describe: 무엇을 먼저 확인하는가? | 4 | 120 |
| 11 | Compare: 어떤 질문인가? | 4 | 120 |
| 12 | Compare: 무엇을 먼저 확인하는가? | 4 | 130 |
| 13 | Predict: 어떤 질문인가? | 4 | 120 |
| 14 | Predict: 무엇을 먼저 확인하는가? | 4 | 120 |
| 15 | Trace: 어떤 질문인가? | 4 | 120 |
| 16 | Trace: 무엇을 먼저 확인하는가? | 4 | 130 |
| 17 | Three Feasibility Questions | 5 | 100 |
| 18 | What We Actually Check | 5 | 100 |
| 19 | Go / Revise / Stop | 5 | 100 |
| 20 | 60-Second Feasibility Demo | 6 | 90 |
| 21 | One-Page Idea Sheet | 6 | 60 |
| 22 | What Happens After Submission | 6 | 70 |
| 23 | Take-Home & Call to Action | 6 | 70 |

The 23 timings total 2,270 seconds, or 37 minutes 50 seconds.

---

### Task 1: Establish reproducible presentation tooling

**Files:**

- Modify: `pyproject.toml`
- Track unchanged: `data/scripts/build_cdm_research_activation_ppt.py`
- Track unchanged: `data/scripts/build_cdm_activation_ppt_v7.py`

- [ ] **Step 1: Capture the current Git and runtime baseline**

Run from the project root:

```powershell
git status --short
git ls-files -- data/scripts/build_cdm_research_activation_ppt.py data/scripts/build_cdm_activation_ppt_v7.py
python --version
python -c "import pptx, PIL, win32com; print(pptx.__version__, PIL.__version__)"
```

Expected: the two builder files are currently untracked, Python is 3.13.x, and the presentation libraries import successfully.

If `.git/packed-refs.lock` exists, verify it is zero bytes, older than the current session, and no `git` process is running before removing only that stale lock. Do not remove it if any Git process is active.

- [ ] **Step 2: Add the presentation dependency group**

Add this exact optional group to `pyproject.toml`:

```toml
presentation = [
    "python-pptx>=1.0.2",
    "Pillow>=12.2.0",
    "pywin32>=312; platform_system == 'Windows'",
]
```

- [ ] **Step 3: Install the declared dependencies**

```powershell
python -m pip install -e ".[dev,presentation]"
```

Expected: installation succeeds and `python -m pytest --version` prints pytest 7 or newer.

- [ ] **Step 4: Prove the legacy builders still work before v8 changes**

```powershell
python data/scripts/build_cdm_research_activation_ppt.py
python data/scripts/build_cdm_activation_ppt_v7.py
python -c "from pptx import Presentation; from pathlib import Path; p=Path('CDM발표'); files=sorted(p.glob('*.pptx'), key=lambda x:x.stat().st_mtime); print([(x.name, len(Presentation(x).slides)) for x in files[-2:]])"
```

Expected: the v6 build has 26 slides and the v7 build has 29 slides.

- [ ] **Step 5: Review and commit only the tooling baseline**

```powershell
git diff --check
git status --short
git add pyproject.toml data/scripts/build_cdm_research_activation_ppt.py data/scripts/build_cdm_activation_ppt_v7.py
git diff --cached --stat
git commit -m "build: track CDM presentation generators"
```

Expected: the commit contains only the dependency declaration and the two existing generators.

---

### Task 2: Build Acts 1–3 with an exact eight-slide contract

**Files:**

- Create: `data/scripts/build_cdm_publishing_strategy_ppt_v8.py`
- Create: `tests/test_cdm_publishing_strategy_ppt_v8.py`
- Read: `CDM발표/edited_subtitle_paper.png`
- Read: local publication CSV files referenced by the v6 `data_summary()` and `validate_examples()` helpers

- [ ] **Step 1: Write the first failing structural tests**

Create tests that import `build_v8`, build to pytest's temporary directory, and assert:

```python
EXPECTED_FIRST_EIGHT = [
    "Publishing Strategy for OMOP CDM-Based Clinical Research",
    "그기 논문이 됩니까?",
    "오늘 답할 두 가지",
    "CDM as Research Infrastructure",
    "Distributed Research Network",
    "Four Question Verbs",
    "From Clinical Question to Study Type",
    "What Has Been Published",
]
```

Also assert that slide 1 contains the approved subtitle, slide 2 contains at least one picture shape, and slide 3 contains both `어떤 연구를 할 수 있는가` and `우리 병원 데이터로 실제 가능한가`.

Run:

```powershell
python -m pytest tests/test_cdm_publishing_strategy_ppt_v8.py -q
```

Expected: collection fails because the v8 module does not exist yet.

- [ ] **Step 2: Create the v8 module and stable content model**

Implement these public contracts:

```python
from dataclasses import dataclass
from pathlib import Path

CDM_DIR = Path(__file__).resolve().parents[2] / "CDM발표"
OUTPUT_V8 = CDM_DIR / "OMOP_CDM_발표자료_v8_publishing_strategy_260713.pptx"
MEME_IMAGE = CDM_DIR / "edited_subtitle_paper.png"

@dataclass(frozen=True)
class TypeSpec:
    verb: str
    study_type: str
    question_pattern: str
    examples: tuple[str, ...]
    required_data: tuple[str, ...]
    feasibility_checks: tuple[str, ...]
    output: str

def build_v8(output_path: Path = OUTPUT_V8, stop_after: int | None = None) -> Path:
    ...
```

`stop_after` is a test seam used only while implementing acts incrementally. It must slice the finished slide list without changing the default 23-slide behavior.

- [ ] **Step 3: Implement slides 1–3**

- Slide 1: use the approved English title and subtitle without adding a second thesis statement.
- Slide 2: place `edited_subtitle_paper.png` prominently and use the title `그기 논문이 됩니까?` as the accessible title/text contract.
- Slide 3: state the two audience questions and the session outcome: each attendee leaves with one clinical topic shaped into a feasibility-review idea.

Keep the approved slide 2 speaker passage in module metadata or notes-source data so the canonical script can reuse it verbatim in Task 5.

- [ ] **Step 4: Implement slides 4–5**

- Slide 4: explain CDM as research infrastructure: standardized data structure, standardized concepts, and reusable analysis logic.
- Slide 5: explain the distributed-network model: code travels, patient-level data stays local, and aggregated evidence returns.

The audience-facing message must answer what CDM enables, not enumerate OMOP tables.

- [ ] **Step 5: Implement slides 6–8 from verified local evidence**

- Slide 6: introduce the four verbs and mappings: Describe/Characterization, Compare/Estimation, Predict/Prediction, Trace/Pathway & Trajectory.
- Slide 7: show how an ordinary clinical question is rewritten around one verb.
- Slide 8: show verified publication evidence and taxonomy counts from the local CSV. Include only examples already enforced by `validate_examples()`.

- [ ] **Step 6: Run the eight-slide tests**

```powershell
python -m pytest tests/test_cdm_publishing_strategy_ppt_v8.py -q
```

Expected: all Act 1–3 tests pass and the temporary presentation opens with eight slides when `stop_after=8`.

- [ ] **Step 7: Commit Acts 1–3**

```powershell
git diff --check
git add data/scripts/build_cdm_publishing_strategy_ppt_v8.py tests/test_cdm_publishing_strategy_ppt_v8.py
git diff --cached --stat
git commit -m "feat: build CDM presentation opening acts"
```

---

### Task 3: Build the eight research-type slides in Act 4

**Files:**

- Modify: `data/scripts/build_cdm_publishing_strategy_ppt_v8.py`
- Modify: `tests/test_cdm_publishing_strategy_ppt_v8.py`

- [ ] **Step 1: Add failing tests for the research-type contract**

Assert that slides 9–16 use these exact titles in this exact order:

```python
EXPECTED_TYPE_TITLES = [
    "Describe: 어떤 질문인가?",
    "Describe: 무엇을 먼저 확인하는가?",
    "Compare: 어떤 질문인가?",
    "Compare: 무엇을 먼저 확인하는가?",
    "Predict: 어떤 질문인가?",
    "Predict: 무엇을 먼저 확인하는가?",
    "Trace: 어떤 질문인가?",
    "Trace: 무엇을 먼저 확인하는가?",
]
```

For each pair, test that the first slide includes a question pattern and a verified publication example, while the second includes required data, feasibility checks, and an expected research output.

Run the targeted tests and confirm they fail because only eight slides exist.

- [ ] **Step 2: Define all four `TypeSpec` records**

Use the following evidence assignments:

- Describe: pneumonia characteristics and troponin testing temporal trends.
- Compare: antidepressants and hyponatremia; SGLT2 inhibitors versus TZD neurodegenerative outcomes.
- Predict: carpal tunnel surgery prediction.
- Trace: urate-lowering therapy sequence in gout; troponin temporal trends where trajectory framing is useful.

Each record must make the difference between the question, required data, feasibility evidence, and likely output explicit.

- [ ] **Step 3: Add reusable pair builders**

Implement:

```python
def slide_type_question(prs: Presentation, spec: TypeSpec) -> None:
    ...

def slide_type_feasibility(prs: Presentation, spec: TypeSpec) -> None:
    ...
```

Use one consistent visual grammar across all four pairs so the audience can compare them without relearning the slide structure.

- [ ] **Step 4: Run the 16-slide structural and evidence tests**

```powershell
python -m pytest tests/test_cdm_publishing_strategy_ppt_v8.py -q
```

Expected: all tests through slide 16 pass, and every cited study is found in the local publication CSV.

- [ ] **Step 5: Commit Act 4**

```powershell
git diff --check
git add data/scripts/build_cdm_publishing_strategy_ppt_v8.py tests/test_cdm_publishing_strategy_ppt_v8.py
git commit -m "feat: add CDM research type menu"
```

---

### Task 4: Build the feasibility decision sequence in Act 5

**Files:**

- Modify: `data/scripts/build_cdm_publishing_strategy_ppt_v8.py`
- Modify: `tests/test_cdm_publishing_strategy_ppt_v8.py`

- [ ] **Step 1: Add failing content tests for slides 17–19**

Test the exact slide titles and required phrases:

- Slide 17: `Can We Define It?`, `Is There Enough Data?`, `Can We Trust the Result?`
- Slide 18: concept sets/cohort logic, attrition and counts, exposure/outcome timing, confounding and data quality.
- Slide 19: `Go`, `Revise`, `Stop`, each with a concrete decision rule.

Run the targeted tests and confirm they fail because the slides are not yet built.

- [ ] **Step 2: Implement slide 17 as the feasibility gateway**

Show the three questions as a sequence, not as independent feature cards. The central message is that a publishable idea must survive all three checks.

- [ ] **Step 3: Implement slide 18 as the feasibility evidence pack**

Define the output of early CDM work as a compact evidence package:

1. operational cohort definitions;
2. attrition and patient counts;
3. observable exposure/outcome windows;
4. covariate coverage and data-quality limitations.

Avoid manuscript-writing or journal-positioning content.

- [ ] **Step 4: Implement slide 19 as an explicit decision**

- Go: definitions are operational, counts support the design, and key bias risks are manageable.
- Revise: the clinical intent is valuable but population, comparison, outcome, or time window must change.
- Stop: the required phenomenon cannot be observed reliably or the usable population is inadequate.

- [ ] **Step 5: Run and commit Act 5**

```powershell
python -m pytest tests/test_cdm_publishing_strategy_ppt_v8.py -q
git diff --check
git add data/scripts/build_cdm_publishing_strategy_ppt_v8.py tests/test_cdm_publishing_strategy_ppt_v8.py
git commit -m "feat: add CDM feasibility decision flow"
```

Expected: the default build reaches 19 tested slides at this stage.

---

### Task 5: Finish Act 6 and write the canonical 37–38 minute script

**Files:**

- Modify: `data/scripts/build_cdm_publishing_strategy_ppt_v8.py`
- Modify: `tests/test_cdm_publishing_strategy_ppt_v8.py`
- Create: `docs/presentations/cdm_speaker_script_v8_260713.md`

- [ ] **Step 1: Add failing tests for the complete 23-slide contract**

Assert:

- exactly 23 slides;
- all titles match the Slide Contract table;
- slide 20 includes `Cohort Definition`, `Generate`, `Completed`, and `Result Collection`;
- slide 21 includes the one-page fields: clinical problem, one verb, population, comparison, outcome, time window, clinical rationale;
- slide 22 shows submission → feasibility review → Go/Revise/Stop feedback;
- slide 23 includes a direct request to submit one clinical topic for feasibility review.

Run and confirm failure at slide 20.

- [ ] **Step 2: Implement slide 20 as a static demo frame**

Create a visually complete fallback with a 45–60 second timeline and a video-frame area. State beneath it:

`자동화는 반복 실행과 결과 수집을 줄입니다. 연구질문과 판단은 연구자의 몫입니다.`

Do not include prompts, model architecture, code, or a live-demo instruction.

- [ ] **Step 3: Implement slides 21–23**

- Slide 21: one-page idea sheet with the seven required fields and one short example.
- Slide 22: show what happens after submission and set a realistic expectation that some ideas will be revised or stopped.
- Slide 23: repeat the core message and the single call to action.

- [ ] **Step 4: Write the canonical speaker script**

Create 23 headings in this exact form:

```markdown
## Slide 1 — Publishing Strategy for OMOP CDM-Based Clinical Research

**Time:** 00:30
```

Use the timing table above. For slide 2, reproduce the approved passage exactly:

```text
여기 계신 연구자분들도 아마 속으로 이런 생각을 하고 계실 겁니다. 사실 저도 다른 강의를 들을 때마다 이 질문부터 했습니다.

“그래서, 그기 논문이 됩니까?”

농담처럼 보이지만 연구자 입장에서는 가장 중요한 질문입니다. CDM이 무엇인지, 데이터가 얼마나 많은지보다 먼저 알고 싶은 건 두 가지입니다.

이걸로 어떤 연구를 할 수 있는가. 그리고 우리 병원 데이터로 실제 가능한가.

오늘은 바로 이 두 질문에 답해 보겠습니다. 그리고 발표가 끝날 때는 각자 관심 있는 주제 하나를 연구질문 초안으로 가져가실 수 있도록 하겠습니다.
```

The script must sound like an experienced research strategist speaking to clinicians, with short transitions and no AI hype.

- [ ] **Step 5: Add script-integrity tests**

Parse the 23 `**Time:** MM:SS` values and assert:

```python
assert len(times) == 23
assert 2220 <= sum(times) <= 2280
```

Also assert that every slide title appears in the corresponding script heading and the slide 2 approved passage remains unchanged.

- [ ] **Step 6: Copy the script beside the deck during a normal build**

After saving the presentation, copy the canonical script to `CDM발표/cdm_speaker_script_v8_260713.md`. The tracked documentation remains the source of truth.

- [ ] **Step 7: Run the complete builder tests and commit**

```powershell
python -m pytest tests/test_cdm_publishing_strategy_ppt_v8.py -q
python data/scripts/build_cdm_publishing_strategy_ppt_v8.py
python -c "from pptx import Presentation; p=Presentation(r'CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713.pptx'); print(len(p.slides))"
```

Expected: tests pass and the command prints `23`.

```powershell
git diff --check
git add data/scripts/build_cdm_publishing_strategy_ppt_v8.py tests/test_cdm_publishing_strategy_ppt_v8.py docs/presentations/cdm_speaker_script_v8_260713.md
git commit -m "feat: complete CDM publishing strategy deck"
```

---

### Task 6: Add video embedding and slide-preview utilities

**Files:**

- Create: `data/scripts/embed_ppt_video.py`
- Create: `data/scripts/render_ppt_preview.py`
- Create: `tests/test_ppt_video_tools.py`

- [ ] **Step 1: Write failing pure-path tests**

Test that the utilities:

- reject a missing input deck with `FileNotFoundError`;
- reject a missing video with `FileNotFoundError`;
- reject slide numbers outside `1..len(slides)` before starting PowerPoint;
- never overwrite the static source deck;
- derive the approved `_with_video.pptx` and `_preview/` output paths.

Keep COM calls behind small functions so path validation can be tested without opening PowerPoint.

- [ ] **Step 2: Implement the video embedder**

Provide this interface:

```python
def embed_video(
    deck_path: Path,
    video_path: Path,
    output_path: Path,
    slide_number: int = 20,
) -> Path:
    ...
```

Use PowerPoint's `Shapes.AddMediaObject2` with `LinkToFile=False`, `SaveWithDocument=True`, and explicit left, top, width, and height values matching the static video frame. Open the static deck, add the media to slide 20, save to the distinct output path, close the presentation, and always quit the COM application in `finally`.

- [ ] **Step 3: Implement the preview renderer**

Provide:

```python
def render_preview(deck_path: Path, output_dir: Path) -> Path:
    ...
```

Use `Presentation.SaveAs(output_dir, 18)` where `18` is `ppSaveAsPNG`. Verify that the number of exported `Slide*.PNG` files equals the deck's slide count.

- [ ] **Step 4: Run non-COM tests**

```powershell
python -m pytest tests/test_ppt_video_tools.py -q
```

Expected: all path and argument tests pass without launching PowerPoint.

- [ ] **Step 5: Run one local COM integration check**

First build the static deck. If the approved MP4 exists, run:

```powershell
python data/scripts/embed_ppt_video.py
python data/scripts/render_ppt_preview.py --deck "CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713_with_video.pptx"
```

If the MP4 is not yet present, render the static deck and confirm that `embed_ppt_video.py` exits with a concise missing-file message. Absence of the external video does not invalidate the static deck.

- [ ] **Step 6: Commit the utilities**

```powershell
git diff --check
git add data/scripts/embed_ppt_video.py data/scripts/render_ppt_preview.py tests/test_ppt_video_tools.py
git commit -m "feat: add PowerPoint media and preview tools"
```

---

### Task 7: Perform final build, visual QA, and handoff

**Files:**

- Verify: all source and test files above
- Generate: all delivery artifacts listed in the File Map

- [ ] **Step 1: Run the full automated verification suite**

```powershell
python -m pytest -q
python data/scripts/build_cdm_research_activation_ppt.py
python data/scripts/build_cdm_activation_ppt_v7.py
python data/scripts/build_cdm_publishing_strategy_ppt_v8.py
```

Expected: all tests pass; v6, v7, and v8 build successfully; their slide counts remain 26, 29, and 23.

- [ ] **Step 2: Verify the final content contract programmatically**

Run a readback that prints slide number, title, and picture/media count. Confirm:

- all 23 titles match the contract;
- slide 2 contains the meme image;
- slide 20 has either the static video frame or an embedded media shape in the postprocessed deck;
- no slide has an empty title contract;
- the canonical and copied scripts are byte-identical;
- script timing totals 2,270 seconds.

- [ ] **Step 3: Render the final preview**

Render the video deck if available; otherwise render the static deck. Confirm exactly 23 PNG files are produced.

- [ ] **Step 4: Inspect every rendered slide visually**

Review the 23 PNGs in order and check:

- no text is clipped, overlapped, or too small for a lecture room;
- visual hierarchy is consistent across the four research-type pairs;
- publication examples are readable and not overloaded;
- the meme retains its humor and does not dominate the entire opening;
- the feasibility sequence reads as a decision flow;
- slide 20 remains understandable with and without video playback;
- the final call to action is visible in under five seconds.

If any slide fails, change the source builder, rebuild, rerender, and repeat the full-slide inspection.

- [ ] **Step 5: Check language and message discipline**

Read the slide text and script aloud once. Confirm:

- the core message appears in the opening and closing;
- CDM capabilities are explained before technical mechanics;
- the terms Describe, Compare, Predict, and Trace are used consistently;
- the script does not drift into manuscript writing, journal selection, or an AI deep dive;
- the final request is one clinical topic submitted as a one-page idea for feasibility review.

- [ ] **Step 6: Verify repository cleanliness and delivery files**

```powershell
git diff --check
git status --short
Get-Item "CDM발표/OMOP_CDM_발표자료_v8_publishing_strategy_260713.pptx"
Get-Item "CDM발표/cdm_speaker_script_v8_260713.md"
```

If the MP4 exists, also verify the `_with_video.pptx` artifact. Generated ignored files should exist on disk but should not appear in the commit.

- [ ] **Step 7: Make a final source-only correction commit if QA required changes**

```powershell
git add pyproject.toml data/scripts tests docs/presentations
git diff --cached --stat
git commit -m "fix: polish CDM presentation delivery"
```

Skip this commit when visual QA required no source changes. Never stage unrelated files.

## Completion Criteria

- The static v8 deck builds reproducibly to exactly 23 slides.
- The slide titles, content, and research examples match the approved design specification.
- The canonical script has exactly 23 timed sections totaling 37 minutes 50 seconds.
- The opening meme and its approved script are present unchanged.
- The audience receives a four-verb research menu and a three-question feasibility decision path.
- The AI demonstration is limited to the agreed short workflow and remains optional for deeper future teaching.
- The one-page idea submission is the sole closing call to action.
- All automated tests pass, the complete deck has been rendered, and all 23 slide images have been visually inspected.
