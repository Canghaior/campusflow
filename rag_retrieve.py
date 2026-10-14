import argparse
import json

from rag_build_index import INDEX_PATH


def load_index() -> dict:
    """只读取已保存的索引，不重新加载原文或构建索引。"""
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(index, dict)
        or index.get("schema_version") != 1
        or index.get("index_type") != "keyword_inverted"
    ):
        raise ValueError("索引格式不匹配，请检查当前索引文件。")

    for field, expected_type in [
        ("keywords", list), ("postings", dict), ("chunks", dict)
    ]:
        if not isinstance(index.get(field), expected_type):
            raise ValueError(f"索引字段 {field} 的类型不正确。")
    return index


def retrieve_chunks(index: dict, question: str, top_k: int = 2) -> list[dict]:
    """按命中的不同关键词数量排序，返回最多 top_k 个候选块。"""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("问题必须是非空文字。")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k 必须是正整数。")

    matches = {}
    # 查询使用保存索引中的词表，与 postings 保持同一份数据。
    for keyword in index["keywords"]:
        if not isinstance(keyword, str) or not keyword:
            raise ValueError("索引词表中存在非法关键词。")
        if keyword not in question:
            continue

        chunk_ids = index["postings"].get(keyword)
        if not isinstance(chunk_ids, list):
            raise ValueError(f"关键词“{keyword}”缺少有效的块编号列表。")

        for chunk_id in chunk_ids:
            if not isinstance(chunk_id, str) or chunk_id not in index["chunks"]:
                raise ValueError("关键词映射引用了不存在或非法的块编号。")
            if chunk_id not in matches:
                matches[chunk_id] = set()
            # 集合只保存不同的词，避免重复词或重复 ID 导致重复计分。
            matches[chunk_id].add(keyword)

    results = []
    for chunk_id, words in matches.items():
        chunk = index["chunks"][chunk_id]
        if (
            not isinstance(chunk, dict)
            or not isinstance(chunk.get("content"), str)
            or not isinstance(chunk.get("metadata"), dict)
        ):
            raise ValueError("候选块缺少有效正文或来源信息。")

        metadata = dict(chunk["metadata"])
        for field in ["source", "filename", "section", "chunk_id"]:
            if not isinstance(metadata.get(field), str) or not metadata[field]:
                raise ValueError(f"候选块来源字段 {field} 不完整。")
        if metadata["chunk_id"] != chunk_id:
            raise ValueError("块编号与来源信息中的编号不一致。")

        results.append({
            "score": len(words),
            "matched_keywords": sorted(words),
            "content": chunk["content"],
            "metadata": metadata,
        })

    # 分数越高越靠前；同分时按块编号排序，让结果顺序可复现。
    results.sort(key=lambda item: (-item["score"], item["metadata"]["chunk_id"]))
    return results[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser(description="检索 CampusFlow 教学关键词索引")
    parser.add_argument("question", help="要检索的问题")
    parser.add_argument("--top-k", type=int, default=2, help="最多返回多少块")
    args = parser.parse_args()

    try:
        index = load_index()
        results = retrieve_chunks(index, args.question, args.top_k)
    except FileNotFoundError:
        raise SystemExit("检索失败：索引文件不存在，请先构建索引。")
    except UnicodeDecodeError:
        raise SystemExit("检索失败：索引文件不是有效的 UTF-8 文本。")
    except (OSError, ValueError) as error:
        raise SystemExit(f"检索失败：{error}")

    if not results:
        print("未检索到候选片段。")
        print("当前关键词索引未找到匹配项，无法仅凭本次结果确认。")
        return

    print(f"候选块数：{len(results)}")
    for result in results:
        metadata = result["metadata"]
        print(f"\n分数：{result['score']}")
        print(f"匹配词：{'、'.join(result['matched_keywords'])}")
        print(f"块ID：{metadata['chunk_id']}")
        print(f"来源：{metadata['source']}")
        print(f"章节：{metadata['section']}")
        print("正文：")
        print(result["content"])


if __name__ == "__main__":
    main()