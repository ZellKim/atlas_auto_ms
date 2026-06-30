"""
render_docx_qa.py — 캐노니컬 DOCX 렌더 QA 도구 (글로벌 자산).

연구마다 반복되는 "원고 DOCX를 렌더해서 시각/구조 QA" 작업의 표준 도구.
DOCX(또는 이미 만든 PDF) → PDF → page_XX.png + contact_sheet.png + qa_report.md.

## 왜 이 도구가 필요한가
- 매 제출 원고마다 page 렌더 + 시각 검토(클리핑/overlap/mojibake)를 함.
- 과거엔 LibreOffice + pypdfium2를 매번 즉석으로 엮어 썼고, soffice 부재/Word COM
  데드락 같은 환경 함정에 반복적으로 빠졌음. 이 도구가 백엔드 폴백을 캡슐화함.

## 백엔드 (auto 모드 우선순위: word → soffice → chrome)
- word    : MS Word COM (ExportAsFixedFormat). **최고 충실도** — reviewer가 Word로
            열었을 때의 실제 페이지 레이아웃 그대로. 첫 export는 PDF 엔진 cold-start로
            이미지 많은 문서에서 60~120초 걸릴 수 있으니 timeout 넉넉히(기본 180s).
            timeout 가드로 정말 멈춰도 다음 백엔드 자동 폴백.
            (2026-06-30: 빈 문서 hang은 데드락이 아니라 짧은 대기로 cold-start를 잘라먹은
            오진이었음. subprocess + 120s timeout으로 정상 렌더 확인.)
- soffice : LibreOffice headless `--convert-to pdf`. 설치돼 있으면 빠르고 충실.
- chrome  : DOCX→HTML(mammoth)→Chrome/Edge `--headless --print-to-pdf`. 브라우저만
            있으면 어디서든 동작(최종 폴백). 단, HTML 재배치라 Word 페이지 레이아웃과
            pixel 일치는 아님 (내용·표·그림·mojibake 검수에는 충분).

## 사용 예
    python data/scripts/render_docx_qa.py path/to/ms.docx
    python data/scripts/render_docx_qa.py ms.docx --out render_qa_ms --dpi 150
    python data/scripts/render_docx_qa.py ms.docx --backend chrome
    python data/scripts/render_docx_qa.py already.pdf            # PDF면 변환 건너뜀

출력 폴더 기본값: <docx와 같은 디렉터리>/render_qa_<stem>/
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 백엔드 탐지
# ---------------------------------------------------------------------------

SOFFICE_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
]
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def _first_existing(candidates: list[str]) -> str | None:
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice") or _first_existing(SOFFICE_CANDIDATES)


def find_chrome() -> str | None:
    return (
        shutil.which("chrome")
        or shutil.which("msedge")
        or shutil.which("chromium")
        or _first_existing(CHROME_CANDIDATES)
    )


def has_word() -> bool:
    """Windows + Word COM 등록 여부 (실제 렌더 성공은 보장 못 함 — timeout 가드 필수)."""
    if os.name != "nt":
        return False
    try:
        import winreg  # noqa: F401

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application"):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# DOCX -> PDF (백엔드별)
# ---------------------------------------------------------------------------


def convert_soffice(docx: Path, out_pdf: Path, timeout: int) -> bool:
    soffice = find_soffice()
    if not soffice:
        return False
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    # soffice는 outdir에 <stem>.pdf로 씀
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_pdf.parent), str(docx)]
    try:
        subprocess.run(cmd, timeout=timeout, check=True, capture_output=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False
    produced = out_pdf.parent / (docx.stem + ".pdf")
    if produced.exists():
        if produced.resolve() != out_pdf.resolve():
            produced.replace(out_pdf)
        return True
    return False


_WORD_PS = r"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {{
  $doc = $word.Documents.Open('{docx}', $false, $true, $false)
  $doc.ExportAsFixedFormat('{pdf}', 17, $false)
  $doc.Close($false)
}} finally {{
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
"""


def convert_word(docx: Path, out_pdf: Path, timeout: int) -> bool:
    """MS Word COM. 첫 export는 PDF 엔진 cold-start로 느릴 수 있음 → timeout 넉넉히.
    timeout 초과 시 좀비 WINWORD 정리 후 폴백."""
    if not has_word():
        return False
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if out_pdf.exists():
        out_pdf.unlink()
    ps = _WORD_PS.format(docx=str(docx).replace("'", "''"), pdf=str(out_pdf).replace("'", "''"))
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            timeout=timeout,
            check=True,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # hang 시 좀비 WINWORD 정리
        if os.name == "nt":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Stop-Process -Name WINWORD -Force -ErrorAction SilentlyContinue"],
                capture_output=True,
            )
        return out_pdf.exists() and out_pdf.stat().st_size > 0
    return out_pdf.exists() and out_pdf.stat().st_size > 0


def convert_chrome(docx: Path, out_pdf: Path, timeout: int) -> bool:
    """DOCX -> HTML(mammoth, 이미지 임베드) -> Chrome/Edge headless print-to-pdf."""
    chrome = find_chrome()
    if not chrome:
        return False
    try:
        import mammoth
    except ImportError:
        return False
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    html_path = out_pdf.with_suffix(".src.html")
    with docx.open("rb") as fh:
        result = mammoth.convert_to_html(fh)
    # 인쇄 여백/표 깨짐 방지용 최소 스타일
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>@page{size:A4;margin:18mm}"
        "body{font-family:'Calibri','Malgun Gothic',sans-serif;font-size:11pt;line-height:1.4}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:3px 5px;font-size:9pt}"
        "img{max-width:100%}</style></head><body>" + result.value + "</body></html>"
    )
    html_path.write_text(html, encoding="utf-8")
    url = html_path.resolve().as_uri()
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out_pdf}",
        url,
    ]
    try:
        subprocess.run(cmd, timeout=timeout, check=True, capture_output=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # 일부 빌드는 --headless=new 미지원 → 구형 플래그 재시도
        cmd[1] = "--headless"
        try:
            subprocess.run(cmd, timeout=timeout, check=True, capture_output=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    return out_pdf.exists() and out_pdf.stat().st_size > 0


BACKENDS = {"soffice": convert_soffice, "word": convert_word, "chrome": convert_chrome}
# word 우선: MS Word가 reviewer가 보는 실제 페이지 레이아웃 그대로 렌더 → 최고 충실도.
# soffice 차선(설치 시), chrome 최종 폴백(브라우저만 있으면 어디서든).
AUTO_ORDER = ["word", "soffice", "chrome"]


def docx_to_pdf(docx: Path, out_pdf: Path, backend: str, word_timeout: int, timeout: int) -> str:
    """선택/auto 백엔드로 변환. 성공한 백엔드명 반환, 실패 시 RuntimeError."""
    order = AUTO_ORDER if backend == "auto" else [backend]
    tried = []
    for name in order:
        fn = BACKENDS[name]
        t = word_timeout if name == "word" else timeout
        tried.append(name)
        print(f"[render] trying backend={name} (timeout={t}s) ...", flush=True)
        if fn(docx, out_pdf, t):
            print(f"[render] OK via {name}", flush=True)
            return name
        print(f"[render] backend={name} unavailable/failed", flush=True)
    raise RuntimeError(f"DOCX->PDF 실패. 시도한 백엔드: {tried}. "
                       f"LibreOffice 설치 또는 대화형 Word에서 PDF 저장 후 --backend 없이 PDF를 직접 넘기세요.")


# ---------------------------------------------------------------------------
# PDF -> PNG + contact sheet
# ---------------------------------------------------------------------------


def pdf_to_pngs(pdf: Path, out_dir: Path, dpi: int) -> list[Path]:
    import pypdfium2 as pdfium

    scale = dpi / 72.0
    doc = pdfium.PdfDocument(str(pdf))
    pages: list[Path] = []
    n = len(doc)
    for i in range(n):
        page = doc[i]
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
        p = out_dir / f"page_{i + 1:02d}.png"
        pil.save(p)
        pages.append(p)
    doc.close()
    print(f"[render] {n} pages -> PNG @ {dpi}dpi", flush=True)
    return pages


def make_contact_sheet(pages: list[Path], out_path: Path, cols: int = 3, thumb_w: int = 520) -> None:
    from PIL import Image

    if not pages:
        return
    thumbs = []
    for p in pages:
        im = Image.open(p).convert("RGB")
        ratio = thumb_w / im.width
        thumbs.append(im.resize((thumb_w, int(im.height * ratio))))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(t.height for t in thumbs)
    pad = 10
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * pad, rows * cell_h + (rows + 1) * pad), "white")
    for idx, t in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = pad + c * (thumb_w + pad)
        y = pad + r * (cell_h + pad)
        sheet.paste(t, (x, y))
    sheet.save(out_path)
    print(f"[render] contact sheet -> {out_path.name}", flush=True)


# ---------------------------------------------------------------------------
# 텍스트/구조 QA
# ---------------------------------------------------------------------------


def text_structure_qa(docx: Path) -> dict:
    qa: dict = {"is_docx": docx.suffix.lower() == ".docx"}
    if not qa["is_docx"]:
        return qa
    # mojibake/깨짐 스캔: document.xml 원문에서 직접
    bad = {"replacement_char": 0, "literal_qq": 0}
    try:
        with zipfile.ZipFile(docx) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        bad["replacement_char"] = xml.count("�")
        # 표시용 '??'는 본문 텍스트에서만 의미 → python-docx로 본문 추출해 카운트
    except Exception:
        pass
    try:
        import docx as _docx

        d = _docx.Document(str(docx))
        full_text = "\n".join(p.text for p in d.paragraphs)
        for t in d.tables:
            for row in t.rows:
                for cell in row.cells:
                    full_text += "\n" + cell.text
        bad["literal_qq"] = full_text.count("??")
        qa["paragraphs"] = len(d.paragraphs)
        qa["tables"] = len(d.tables)
        qa["table_shapes"] = [f"{len(t.rows)}x{len(t.columns)}" for t in d.tables]
        qa["sections"] = len(d.sections)
        orient = {0: "portrait", 1: "landscape"}
        qa["orientations"] = [orient.get(int(s.orientation), str(s.orientation)) for s in d.sections]
    except Exception as e:  # python-docx 없거나 파싱 실패
        qa["structure_note"] = f"python-docx 미사용/실패: {e}"
    qa["mojibake"] = bad
    return qa


def write_report(out_dir: Path, docx: Path, backend: str, pdf: Path, pages: list[Path], qa: dict, dpi: int) -> Path:
    rpt = out_dir / "qa_report.md"
    lines = [
        f"# Render QA — {docx.name}",
        "",
        f"- Source: `{docx}`",
        f"- Backend: **{backend}**",
        f"- PDF: `{pdf.name}` ({pdf.stat().st_size:,} bytes)",
        f"- Pages rendered: **{len(pages)}** @ {dpi} dpi (`page_01.png` …)",
        f"- Contact sheet: `contact_sheet.png`",
        "",
        "## Text / structure",
    ]
    if qa.get("is_docx"):
        if "paragraphs" in qa:
            lines += [
                f"- Paragraphs: {qa['paragraphs']}",
                f"- Tables: {qa['tables']} — shapes {qa.get('table_shapes')}",
                f"- Sections: {qa['sections']} — orientation {qa.get('orientations')}",
            ]
        if "structure_note" in qa:
            lines.append(f"- {qa['structure_note']}")
        mb = qa.get("mojibake", {})
        flag = "PASS" if mb.get("replacement_char", 0) == 0 and mb.get("literal_qq", 0) == 0 else "**CHECK**"
        lines.append(
            f"- Mojibake scan: {flag} — U+FFFD={mb.get('replacement_char', 0)}, literal '??'={mb.get('literal_qq', 0)}"
        )
    else:
        lines.append("- (입력이 PDF라 구조 스캔 생략)")
    lines += [
        "",
        "## Visual review checklist (수동)",
        "- [ ] Title page / author line",
        "- [ ] Figures (clipping/overlap 없음)",
        "- [ ] Tables (열 잘림/줄바꿈 깨짐 없음)",
        "- [ ] Discussion / References 가독성",
        "",
        f"> 백엔드가 `chrome`이면 HTML 재배치 렌더라 Word 페이지 레이아웃과 pixel 일치하지 않음. "
        f"제출 직전 pixel-exact 검수는 대화형 Word 또는 LibreOffice 권장.",
        "",
    ]
    rpt.write_text("\n".join(lines), encoding="utf-8")
    print(f"[render] report -> {rpt.name}", flush=True)
    return rpt


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DOCX 렌더 QA (PDF + page PNG + contact sheet + 구조 스캔)")
    ap.add_argument("input", help=".docx 또는 .pdf 경로")
    ap.add_argument("--out", help="출력 폴더 (기본: <입력 디렉터리>/render_qa_<stem>/)")
    ap.add_argument("--backend", choices=["auto", "soffice", "word", "chrome"], default="auto")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--cols", type=int, default=3, help="contact sheet 열 수")
    ap.add_argument("--timeout", type=int, default=180, help="soffice/chrome 변환 timeout(초)")
    ap.add_argument("--word-timeout", type=int, default=180,
                    help="Word COM timeout(초); 초과 시 폴백. 첫 ExportAsFixedFormat 호출은 PDF 엔진 "
                         "cold-start로 이미지 많은 문서에서 60~120초 걸릴 수 있어 넉넉히 잡음")
    args = ap.parse_args(argv)

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        print(f"입력 없음: {src}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser().resolve() if args.out else src.parent / f"render_qa_{src.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() == ".pdf":
        pdf = out_dir / src.name
        if pdf.resolve() != src.resolve():
            shutil.copy2(src, pdf)
        backend = "pdf-input"
    else:
        pdf = out_dir / (src.stem + ".pdf")
        backend = docx_to_pdf(src, pdf, args.backend, args.word_timeout, args.timeout)

    pages = pdf_to_pngs(pdf, out_dir, args.dpi)
    make_contact_sheet(pages, out_dir / "contact_sheet.png", cols=args.cols)
    qa = text_structure_qa(src)
    write_report(out_dir, src, backend, pdf, pages, qa, args.dpi)

    print(f"\n[render] DONE -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
