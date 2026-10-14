import argparse
import json

from rag_chunk_document import split_document
from rag_load_document import DEFAULT_SOURCE, PROJECT_DIR, load_document


# 教学词表：本次只记录这些词在各块中是否出现。
KEYWORDS = [
    "提交", "时间", "18:00", "审核",
    "任课教师", "生效", "课程编号", "退课原因",
]
INDEX_PATH = PROJECT_DIR / "data" / "index" / "keyword_index.json"


def build_keyword_index(chunks: list[dict]) -> dict:
    """建立关键词到块编号的映射，并保留每块的正文与来源。"""
    if not chunks:
        raise ValueError("没有文档块，无法构建索引。")

    chunk_by_id = {}
    postings = {}
    for keyword in KEYWORDS:
        postings[keyword] = []

    for chunk in chunks:
        chunk_id = chunk["metadata"]["chunk_id"]
        if chunk_id in chunk_by_id:
            raise ValueError(f"发现重复的块编号：{chunk_id}")
        chunk_by_id[chunk_id] = chunk

        # 子串匹配只表示词出现；这里还没有回答问题或判断证据充分性。
        for keyword in KEYWORDS:
            if keyword in chunk["content"]:
                postings[keyword].append(chunk_id)

    # 块与关键词映射来自同一次切分，一起保存。
    return {
        "schema_version": 1,
        "index_type": "keyword_inverted",
        "keywords": KEYWORDS,
        "chunking_rule": "按行首二级标题切分，保留公共前言",
        "chunks": chunk_by_id,
        "postings": postings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 CampusFlow 教学关键词索引")
    parser.add_argument("path", nargs="?", default=DEFAULT_SOURCE)
    args = parser.parse_args()

    try:
        document = load_document(args.path)
        chunks = split_document(document)
        index = build_keyword_index(chunks)

        # 创建输出目录；已有目录可以继续使用。
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 序列化成 JSON 文本，再整体写入生成文件；重建时替换旧结果。
        index_text = json.dumps(index, ensure_ascii=False, indent=2)
        INDEX_PATH.write_text(index_text, encoding="utf-8")

        # 从磁盘读回，核对保存后的 JSON 可以还原为字典。
        saved_index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

        # 每个关键词记录的块编号，都必须能找到对应块。
        for keyword, chunk_ids in saved_index["postings"].items():
            for chunk_id in chunk_ids:
                if chunk_id not in saved_index["chunks"]:
                    raise ValueError(f"关键词“{keyword}”引用了不存在的块。")

    except FileNotFoundError:
        raise SystemExit("索引构建失败：资料文件不存在，请检查路径。")
    except UnicodeDecodeError:
        raise SystemExit("索引构建失败：资料文件不是有效的 UTF-8 文本。")
    except (OSError, ValueError) as error:
        raise SystemExit(f"索引构建失败：{error}")

    source = INDEX_PATH.relative_to(PROJECT_DIR).as_posix()
    print(f"索引已保存：{source}")
    print(f"文档块数：{len(saved_index['chunks'])}")
    print("读回核对：所有关键词映射均指向已有文档块")
    for keyword in ["审核", "课程编号"]:
        print(f"关键词“{keyword}”对应的块：")
        for chunk_id in saved_index["postings"][keyword]:
            print(f"  {chunk_id}")


if __name__ == "__main__":
    main()