#!/usr/bin/env python3
"""
Kindle の表示領域を連続スクショし、1 冊分の PDF にまとめるツール。

使い方の流れ:
  1. Kindle アプリで対象の本を開き、1 ページ目を表示する
  2. 本スクリプトを実行し、カウントダウン中に Kindle ウィンドウを最前面にする
  3. 指定ページ数ぶんスクショ → ページ送りを繰り返す
  4. output/ に PNG と PDF が保存される

macOS では「システム設定 → プライバシーとセキュリティ → 画面収録とシステムオーディオ」
でターミナル（または Cursor）に画面収録を許可してください。

個人で購入・利用権のあるコンテンツのバックアップ用途を想定しています。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyautogui
from PIL import Image

# マウスを画面左上に移動すると緊急停止（pyautogui のフェイルセーフ）
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def parse_region(value: str) -> tuple[int, int, int, int]:
    """'x,y,width,height' 形式をパースする。"""
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "領域は 'x,y,width,height' 形式で指定してください（例: 100,80,1200,900）"
        )
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("領域の各値は整数である必要があります") from exc
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("width と height は正の整数にしてください")
    return x, y, w, h


def parse_point(value: str) -> tuple[int, int]:
    """'x,y' 形式をパースする。"""
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("座標は 'x,y' 形式で指定してください（例: 1500,600）")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("座標は整数である必要があります") from exc


def countdown(seconds: int) -> None:
    print(f"\n{seconds} 秒後に開始します。Kindle を最前面にしてください。")
    for remaining in range(seconds, 0, -1):
        print(f"  {remaining}...")
        time.sleep(1)
    print("開始\n")


def capture_region(region: tuple[int, int, int, int]) -> Image.Image:
    shot = pyautogui.screenshot(region=region)
    return shot.convert("RGB")


def turn_page(
    method: str,
    click_point: tuple[int, int] | None,
    key: str,
) -> None:
    if method == "click":
        if click_point is None:
            raise ValueError("click 方式では --click-point が必要です")
        pyautogui.click(click_point[0], click_point[1])
    elif method == "key":
        pyautogui.press(key)
    else:
        raise ValueError(f"不明なページ送り方式: {method}")


def images_to_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    if not image_paths:
        raise ValueError("PDF にする画像がありません")

    pages: list[Image.Image] = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        pages.append(img)

    first, *rest = pages
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    first.save(
        pdf_path,
        "PDF",
        resolution=150.0,
        save_all=True,
        append_images=rest,
    )
    for img in pages:
        img.close()


def pick_region_interactive() -> tuple[int, int, int, int]:
    """マウス位置から撮影領域の目安を取る（対話モード）。"""
    print("撮影領域の左上にマウスを置いて Enter...")
    input()
    x1, y1 = pyautogui.position()
    print(f"  左上: ({x1}, {y1})")

    print("撮影領域の右下にマウスを置いて Enter...")
    input()
    x2, y2 = pyautogui.position()
    print(f"  右下: ({x2}, {y2})")

    left, top = min(x1, x2), min(y1, y2)
    width, height = abs(x2 - x1), abs(y2 - y1)
    if width < 10 or height < 10:
        print("領域が小さすぎます。", file=sys.stderr)
        sys.exit(1)

    region = (left, top, width, height)
    print(f"  → 領域: {region[0]},{region[1]},{region[2]},{region[3]}")
    return region


def pick_click_interactive() -> tuple[int, int]:
    print("「次のページ」を送るクリック位置にマウスを置いて Enter...")
    input()
    pos = pyautogui.position()
    print(f"  クリック位置: ({pos.x}, {pos.y})")
    return pos.x, pos.y


def run(args: argparse.Namespace) -> None:
    if args.setup_region:
        region = pick_region_interactive()
        print("\n次回は次のオプションで実行してください:")
        print(
            f"  --region {region[0]},{region[1]},{region[2]},{region[3]}"
        )
        return

    if args.setup_click:
        x, y = pick_click_interactive()
        print("\n次回は次のオプションで実行してください:")
        print(f"  --turn click --click-point {x},{y}")
        return

    region = args.region
    if region is None:
        print(
            "エラー: --region が未指定です。先に --setup-region で領域を調べてください。",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    click_point = args.click_point
    if args.turn == "click" and click_point is None:
        print(
            "エラー: --turn click のときは --click-point か --setup-click が必要です。",
            file=sys.stderr,
        )
        sys.exit(1)

    countdown(args.countdown)

    image_paths: list[Path] = []
    total = args.pages

    for page in range(1, total + 1):
        print(f"[{page}/{total}] スクショ中...", end=" ", flush=True)
        img = capture_region(region)
        png_path = output_dir / f"page_{page:04d}.png"
        img.save(png_path, "PNG")
        image_paths.append(png_path)
        print(f"保存 → {png_path.name}")

        if page < total:
            time.sleep(args.delay_before_turn)
            turn_page(args.turn, click_point, args.key)
            time.sleep(args.delay_after_turn)

    pdf_path = output_dir / args.pdf_name
    print(f"\nPDF を作成中: {pdf_path}")
    images_to_pdf(image_paths, pdf_path)
    print(f"完了: {pdf_path}（{len(image_paths)} ページ）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kindle のページを連続スクショして PDF にまとめる",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  # 1) 撮影領域を対話で取得
  python kindle_to_pdf.py --setup-region

  # 2) 120 ページ、右矢印で送る（領域は取得した値に置き換え）
  python kindle_to_pdf.py --region 100,80,1200,900 --pages 120 --turn key --key right

  # 3) 画面右側をクリックしてページ送り
  python kindle_to_pdf.py --region 100,80,1200,900 --pages 120 \\
    --turn click --click-point 1500,600
        """,
    )
    parser.add_argument(
        "--region",
        type=parse_region,
        help="スクショ領域 x,y,width,height（--setup-region で調べられる）",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=10,
        help="撮影するページ数（既定: 10）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="PNG / PDF の出力先（既定: output）",
    )
    parser.add_argument(
        "--pdf-name",
        default="kindle_book.pdf",
        help="出力 PDF ファイル名（既定: kindle_book.pdf）",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=5,
        help="開始前の待機秒数（既定: 5）",
    )
    parser.add_argument(
        "--delay-before-turn",
        type=float,
        default=0.3,
        help="スクショ後、ページ送りまでの待機秒（既定: 0.3）",
    )
    parser.add_argument(
        "--delay-after-turn",
        type=float,
        default=1.0,
        help="ページ送り後、次のスクショまでの待機秒（既定: 1.0）",
    )
    parser.add_argument(
        "--turn",
        choices=("key", "click"),
        default="key",
        help="ページ送り方法: key=キー入力, click=マウスクリック（既定: key）",
    )
    parser.add_argument(
        "--key",
        default="right",
        help="--turn key 時に送るキー（既定: right）。Kindle では right / space など",
    )
    parser.add_argument(
        "--click-point",
        type=parse_point,
        help="--turn click 時のクリック座標 x,y",
    )
    parser.add_argument(
        "--setup-region",
        action="store_true",
        help="マウス位置から撮影領域を対話的に取得して終了",
    )
    parser.add_argument(
        "--setup-click",
        action="store_true",
        help="マウス位置からクリック座標を対話的に取得して終了",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.pages < 1:
        parser.error("--pages は 1 以上にしてください")

    try:
        run(args)
    except pyautogui.FailSafeException:
        print(
            "\nフェイルセーフ: マウスが画面端に移動したため中断しました。",
            file=sys.stderr,
        )
        sys.exit(130)


if __name__ == "__main__":
    main()
