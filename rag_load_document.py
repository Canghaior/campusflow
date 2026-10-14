import argparse
from pathlib import Path


# 按脚本自身的位置确定项目目录，避免依赖终端当前目录。
PROJECT_DIR = Path(__file__).resolve().parent
DOCUMENT_DIR = PROJECT_DIR / "data" / "public_docs"
DEFAULT_SOURCE = "data/public_docs/drop_course_policy.md"


def load_document(relative_path: str) -> dict:
    """读取一份模拟 Markdown 资料，返回正文与来源信息。"""
    input_path = Path(relative_path)
    if input_path.is_absolute():
        raise ValueError("请传入相对于项目根目录的资料路径。")

    file_path = (PROJECT_DIR / input_path).resolve()

    # 读取前限定资料目录；这里的 relative_to 会拒绝目录外的路径。
    try:
        file_path.relative_to(DOCUMENT_DIR)
        source = file_path.relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        raise ValueError("只允许读取 data/public_docs 中的资料。") from None

    if file_path.suffix.lower() != ".md":
        raise ValueError("本次只加载 .md 格式的模拟资料。")

    # utf-8-sig 兼容普通 UTF-8，也会去掉文件开头的 UTF-8 编码标记。
    content = file_path.read_text(encoding="utf-8-sig")

    # strip 只用于检查空白；返回时仍保留读取到的完整正文。
    if not content.strip():
        raise ValueError("资料文件为空或只有空白。")

    return {
        "content": content,
        "metadata": {
            "source": source,
            "filename": file_path.name,
        },
    }


def main() -> None:
    # 读取命令后面的可选资料路径；不传时使用默认模拟退课规则。
    parser = argparse.ArgumentParser(description="加载 CampusFlow 模拟规则文档")
    parser.add_argument("path", nargs="?", default=DEFAULT_SOURCE)
    args = parser.parse_args()

    try:
        document = load_document(args.path)
    except FileNotFoundError:
        raise SystemExit("加载失败：资料文件不存在，请检查路径。")
    except UnicodeDecodeError:
        raise SystemExit("加载失败：资料文件不是有效的 UTF-8 文本。")
    except (OSError, ValueError) as error:
        raise SystemExit(f"加载失败：{error}")

    # 显示结果，方便核对正文与来源是否都被保留下来。
    metadata = document["metadata"]
    print("加载成功")
    print(f"来源：{metadata['source']}")
    print(f"文件名：{metadata['filename']}")
    print("正文：")
    print(document["content"])


if __name__ == "__main__":
    main()