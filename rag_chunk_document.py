import argparse

from rag_load_document import DEFAULT_SOURCE, load_document


def split_document(document: dict) -> list[dict]:
    """按行首的二级标题切分当前格式的模拟规则文档。"""
    text = document["content"]
    if not text.strip():
        raise ValueError("文档正文为空，无法切块。")

    preamble_lines = []  # 第一个条款前的标题、模拟声明和版本。
    sections = []       # 每项保存：条款标题、本条正文。
    current_title = None
    current_lines = []

    # 逐行读取；遇到新的二级标题时，保存上一条。
    for line in text.splitlines():
        if line.startswith("## "):
            if current_title is not None:
                body = "\n".join(current_lines).strip()
                sections.append((current_title, body))

            current_title = line[3:].strip()
            if not current_title:
                raise ValueError("二级标题不能为空。")
            current_lines = []
        elif current_title is None:
            preamble_lines.append(line)
        else:
            current_lines.append(line)

    # 循环结束后，最后一条还需要保存。
    if current_title is None:
        sections = [("全文", text)]
        preamble = ""
    else:
        body = "\n".join(current_lines).strip()
        sections.append((current_title, body))
        preamble = "\n".join(preamble_lines).strip()

    chunks = []
    for index, (section_title, body) in enumerate(sections, start=1):
        # 先检查本条正文，避免公共前言掩盖空条款。
        if not body.strip():
            raise ValueError(f"“{section_title}”只有标题，没有正文。")

        if current_title is None:
            chunk_content = body
        else:
            chunk_content = f"## {section_title}\n\n{body}"
            if preamble:
                chunk_content = f"{preamble}\n\n{chunk_content}"

        # 为每个块复制来源信息，避免修改原文档的 metadata。
        metadata = dict(document["metadata"])
        metadata["section"] = section_title
        metadata["chunk_id"] = f"{metadata['source']}#chunk-{index}"
        chunks.append({"content": chunk_content, "metadata": metadata})

    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="按条款切分 CampusFlow 模拟规则")
    parser.add_argument("path", nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument(
        "--demo-no-heading",
        action="store_true",
        help="使用没有二级标题的内存示例",
    )
    args = parser.parse_args()

    try:
        if args.demo_no_heading:
            # 这是内存中的模拟输入，不需要创建新的资料文件。
            document = {
                "content": "这是一段没有二级标题的模拟说明。\n用于验证全文保留为一个块。",
                "metadata": {
                    "source": "memory:no_heading_demo",
                    "filename": "内存示例",
                },
            }
        else:
            document = load_document(args.path)

        chunks = split_document(document)
    except FileNotFoundError:
        raise SystemExit("切块失败：资料文件不存在，请检查路径。")
    except UnicodeDecodeError:
        raise SystemExit("切块失败：资料文件不是有效的 UTF-8 文本。")
    except (OSError, ValueError) as error:
        raise SystemExit(f"切块失败：{error}")

    print(f"块数：{len(chunks)}")
    for chunk in chunks:
        metadata = chunk["metadata"]
        print(f"\n块ID：{metadata['chunk_id']}")
        print(f"章节：{metadata['section']}")
        print(f"来源：{metadata['source']}")
        print("正文：")
        print(chunk["content"])


if __name__ == "__main__":
    main()