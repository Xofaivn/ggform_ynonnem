from __future__ import annotations

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import (
    KeywordRule,
    RunConfig,
    TextRule,
    list_profiles,
    load_profile,
    save_profile,
)

console = Console()

BANNER = """[bold cyan]
   ██████╗  ██████╗ ██████╗ ███╗   ███╗    ███████╗██╗██╗     ██╗     ███████╗██████╗
  ██╔════╝ ██╔═══╝██╔═══██╗████╗ ████║    ██╔════╝██║██║     ██║     ██╔════╝██╔══██╗
  ██║  ███╗██║    ██║   ██║██╔████╔██║    █████╗  ██║██║     ██║     █████╗  ██████╔╝
  ██║   ██║██║    ██║   ██║██║╚██╔╝██║    ██╔══╝  ██║██║     ██║     ██╔══╝  ██╔══██╗
  ╚██████╔╝╚█████╗╚██████╔╝██║ ╚═╝ ██║    ██║     ██║███████╗███████╗███████╗██║  ██║
   ╚═════╝  ╚════╝ ╚═════╝ ╚═╝     ╚═╝    ╚═╝     ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝
[/bold cyan]"""


def _print_banner() -> None:
    console.print(BANNER)
    console.print(Panel("[bold]Google Form Auto-Filler[/bold] · v3.0", expand=False))
    console.print()


def _ask(prompt: str, default: str = "", validate=None) -> str:
    """Hỏi 1 câu với questionary text."""
    kwargs = {"message": prompt, "default": default}
    if validate:
        kwargs["validate"] = validate
    return questionary.text(**kwargs).ask() or default


def _ask_int(prompt: str, default: int, min_val: int = 1, max_val: int = 9999) -> int:
    def val(v):
        try:
            n = int(v)
            if min_val <= n <= max_val:
                return True
            return f"Nhập số từ {min_val} đến {max_val}"
        except ValueError:
            return "Phải là số nguyên"

    r = questionary.text(prompt, default=str(default), validate=val).ask()
    return int(r) if r else default


def _ask_float(prompt: str, default: float, min_val: float = 0.0) -> float:
    def val(v):
        try:
            n = float(v)
            if n >= min_val:
                return True
            return f"Phải >= {min_val}"
        except ValueError:
            return "Phải là số thực"

    r = questionary.text(prompt, default=str(default), validate=val).ask()
    return float(r) if r else default


def _ask_confirm(prompt: str, default: bool = False) -> bool:
    return questionary.confirm(prompt, default=default).ask() or False


def _collect_keyword_rules() -> list[KeywordRule]:
    """Hỏi người dùng nhập các KeywordRule (cho radio/checkbox)."""
    rules: list[KeywordRule] = []
    console.print("\n[bold yellow]⚙ Keyword Rules[/bold yellow] (dùng để ưu tiên đáp án cho radio/checkbox)")
    console.print("  Cách dùng:")
    console.print("    • [cyan]Question keyword[/cyan] = cụm từ xuất hiện trong câu hỏi")
    console.print("      Ví dụ: câu hỏi là 'Bạn thường mua sắm ở đâu?' → keyword = 'mua sắm'")
    console.print("    • [cyan]Preferred answers[/cyan] = đáp án muốn ưu tiên chọn (dùng dấu phẩy nếu nhiều)")
    console.print("      Ví dụ: preferred = 'Online, Shopee' → ưu tiên chọn đáp án chứa 'Online' hoặc 'Shopee'")
    console.print("    • [cyan]Tỉ lệ[/cyan] = 1.0 luôn chọn, 0.7 = 70% chọn theo keyword, 30% random\n")

    while True:
        add = _ask_confirm("  Thêm keyword rule?", default=len(rules) == 0)
        if not add:
            break

        kw = _ask("    Question keyword (khớp với label câu hỏi): ")
        if not kw.strip():
            continue

        answers_raw = _ask("    Preferred answers (cách nhau dấu phẩy): ")
        preferred = [a.strip() for a in answers_raw.split(",") if a.strip()]
        if not preferred:
            console.print("    [yellow]Bỏ qua — không có preferred answers[/yellow]")
            continue

        ratio_str = _ask("    Tỉ lệ áp dụng rule (0.0–1.0, mặc định 1.0): ", default="1.0")
        try:
            ratio = float(ratio_str)
            ratio = max(0.0, min(1.0, ratio))
        except ValueError:
            ratio = 1.0

        rules.append(KeywordRule(question_keyword=kw.strip(), preferred_answers=preferred, ratio=ratio))
        console.print(f"    [green]✓ Đã thêm rule:[/green] '{kw}' → {preferred} (ratio={ratio})")

    return rules


def _collect_text_rules() -> list[TextRule]:
    """Hỏi người dùng nhập các TextRule (cho paragraph/short answer)."""
    rules: list[TextRule] = []
    console.print("\n[bold yellow]⚙ Text Rules[/bold yellow] (đoạn văn cho câu hỏi tự luận)")
    console.print("  Ví dụ: keyword = 'feedback', rồi nhập từng đoạn văn muốn paste\n")

    while True:
        add = _ask_confirm("  Thêm text rule?", default=len(rules) == 0)
        if not add:
            break

        kw = _ask("    Question keyword (khớp với label câu hỏi): ")
        if not kw.strip():
            continue

        answers: list[str] = []
        console.print("    Nhập từng đoạn văn (Enter trống để kết thúc):")
        idx = 1
        while True:
            ans = _ask(f"      Đoạn {idx}: ")
            if not ans.strip():
                break
            answers.append(ans.strip())
            idx += 1

        if not answers:
            console.print("    [yellow]Bỏ qua — không có đoạn văn nào[/yellow]")
            continue

        rules.append(TextRule(question_keyword=kw.strip(), answers=answers))
        console.print(f"    [green]✓ Đã thêm rule:[/green] '{kw}' → {len(answers)} đoạn văn")

    return rules


def _show_summary(cfg: RunConfig) -> None:
    """Hiện bảng tóm tắt config."""
    console.print()
    t = Table(title="📋 Tóm tắt cấu hình", show_lines=True, highlight=True)
    t.add_column("Thiết lập", style="bold")
    t.add_column("Giá trị")

    t.add_row("Form URL", cfg.form_url[:70] + ("..." if len(cfg.form_url) > 70 else ""))
    t.add_row("Số lần submit", str(cfg.n_submissions))
    t.add_row("Headless", "Có (ẩn)" if cfg.headless else "Không (hiện cửa sổ)")
    t.add_row("Ngôn ngữ form", cfg.form_language.upper())
    t.add_row("Randomization level", f"{cfg.randomization_level}/5")
    t.add_row("Hướng rating", cfg.rating_direction)
    t.add_row("Delay", f"{cfg.delay_min}–{cfg.delay_max}s")
    t.add_row("Preview mode", "Có (không submit)" if cfg.no_submit else "Không")
    t.add_row("Khoảng ngày", f"{cfg.date_start} → {cfg.date_end}")
    t.add_row("Keyword rules", str(len(cfg.keyword_rules)))
    t.add_row("Text rules", str(len(cfg.text_rules)))
    avoid_str = ", ".join(cfg.avoid_answers) if cfg.avoid_answers else "Không"
    t.add_row("Né đáp án chứa", avoid_str)

    console.print(t)
    console.print()


def _build_new_config() -> RunConfig:
    """Wizard nhập cấu hình mới từ đầu."""
    console.print("[bold]📝 Nhập cấu hình mới:[/bold]\n")

    # 1. Form URL
    def validate_url(v):
        if "google.com/forms" in v or "forms.gle" in v or "docs.google.com/forms" in v:
            return True
        return "URL phải chứa 'google.com/forms' hoặc 'forms.gle'"

    url = questionary.text(
        "1. Form URL:", validate=validate_url
    ).ask() or ""

    # 2. Số lần submit
    n = _ask_int("2. Số lần submit:", default=2, min_val=1)

    # 3. Headless
    headless = _ask_confirm("3. Chạy ẩn Chrome (headless)?", default=False)

    # 4. Ngôn ngữ form
    lang = questionary.select(
        "4. Ngôn ngữ của form:",
        choices=[
            questionary.Choice("Tự động phát hiện", value="auto"),
            questionary.Choice("Tiếng Việt", value="vi"),
            questionary.Choice("Tiếng Anh", value="en"),
        ],
    ).ask() or "auto"

    # 5. Randomization level
    rand_level = questionary.select(
        "5. Mức độ random (1 = theo keyword, 5 = random hoàn toàn):",
        choices=[
            questionary.Choice("1 – Luôn theo keyword (không random)", value=1),
            questionary.Choice("2 – Ưu tiên keyword mạnh (~85%)", value=2),
            questionary.Choice("3 – Cân bằng (~70% keyword) [Mặc định]", value=3),
            questionary.Choice("4 – Nghiêng về random (~50%)", value=4),
            questionary.Choice("5 – Chủ yếu random (~30% keyword)", value=5),
        ],
    ).ask() or 3

    # 6. Hướng rating
    rating = questionary.select(
        "6. Hướng đánh giá (cho Scale/Grid 1–5):",
        choices=[
            questionary.Choice("Positive — ưu tiên điểm cao (4–5)", value="positive"),
            questionary.Choice("Negative — ưu tiên điểm thấp (1–2)", value="negative"),
            questionary.Choice("Neutral — random đều", value="neutral"),
        ],
    ).ask() or "positive"

    # 7. Delay
    console.print("\n7. Delay giữa các lần submit (giây):")
    delay_min = _ask_float("   Min:", default=1.0, min_val=0.0)
    delay_max = _ask_float("   Max:", default=3.0, min_val=delay_min)

    # 8. Preview mode
    no_submit = _ask_confirm("8. Preview mode (không submit thật)?", default=False)

    # 9. Date range
    console.print("\n9. Khoảng ngày cho câu hỏi Date (YYYY-MM-DD):")
    date_start = _ask("    Từ ngày:", default="2020-01-01")
    date_end = _ask("    Đến ngày:", default="2024-12-31")

    # 10. Keyword rules
    keyword_rules = _collect_keyword_rules()

    # 11. Text rules
    text_rules = _collect_text_rules()

    # 12. Avoid answer keywords
    console.print("\n[bold yellow]⚙ Né đáp án[/bold yellow] (không bao giờ chọn đáp án chứa các từ này)")
    console.print("  Ví dụ: 'không biết, không có ý kiến, chưa sử dụng'")
    console.print("  → Bất kỳ đáp án nào chứa các từ trên sẽ bị bỏ qua ở MỌI câu hỏi\n")
    avoid_raw = _ask("  Nhập từ muốn né (cách nhau dấu phẩy, Enter để bỏ qua): ", default="")
    avoid_answers = [k.strip() for k in avoid_raw.split(",") if k.strip()]
    if avoid_answers:
        console.print(f"  [green]✓ Sẽ né đáp án chứa:[/green] {avoid_answers}")

    return RunConfig(
        form_url=url,
        n_submissions=n,
        headless=headless,
        form_language=lang,
        randomization_level=rand_level,
        rating_direction=rating,
        delay_min=delay_min,
        delay_max=delay_max,
        no_submit=no_submit,
        date_start=date_start,
        date_end=date_end,
        keyword_rules=keyword_rules,
        text_rules=text_rules,
        avoid_answers=avoid_answers,
    )


def run_wizard() -> RunConfig:
    """Wizard khởi động chính. Trả về RunConfig đã xác nhận."""
    _print_banner()

    # Hỏi load profile hay tạo mới
    profiles = list_profiles()
    cfg: RunConfig | None = None

    if profiles:
        choice = questionary.select(
            "Bắt đầu từ:",
            choices=[
                questionary.Choice("✨ Tạo cấu hình mới", value="__new__"),
                *[questionary.Choice(f"📁 Profile: {p}", value=p) for p in profiles],
            ],
        ).ask() or "__new__"

        if choice != "__new__":
            try:
                cfg = load_profile(choice)
                console.print(f"[green]✓ Đã tải profile '[bold]{choice}[/bold]'[/green]")

                # Cho phép sửa 1 số field cơ bản sau khi load
                if _ask_confirm("Sửa URL / số lần submit?", default=False):
                    cfg.form_url = questionary.text("Form URL:", default=cfg.form_url).ask() or cfg.form_url
                    cfg.n_submissions = _ask_int("Số lần submit:", default=cfg.n_submissions, min_val=1)
            except Exception as e:
                console.print(f"[red]Lỗi load profile: {e}[/red]")
                cfg = None

    if cfg is None:
        cfg = _build_new_config()

    # Hiện summary và xác nhận
    while True:
        _show_summary(cfg)
        action = questionary.select(
            "Xác nhận?",
            choices=[
                questionary.Choice("🚀 Bắt đầu chạy", value="start"),
                questionary.Choice("💾 Lưu profile rồi chạy", value="save_run"),
                questionary.Choice("✏️  Nhập lại từ đầu", value="redo"),
                questionary.Choice("❌ Thoát", value="exit"),
            ],
        ).ask() or "exit"

        if action == "exit":
            raise SystemExit(0)

        if action == "redo":
            cfg = _build_new_config()
            continue

        if action in ("save_run", "start"):
            if action == "save_run":
                name = _ask("Tên profile (không dùng khoảng trắng): ", default="my_profile")
                name = name.strip().replace(" ", "_")
                if name:
                    path = save_profile(cfg, name)
                    console.print(f"[green]✓ Đã lưu profile → {path}[/green]")
            break

    console.print("\n[bold green]▶ Bắt đầu![/bold green]\n")
    return cfg
