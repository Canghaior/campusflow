import argparse
import json
import math

from fastembed import TextEmbedding

from rag_build_vector_index import INDEX_PATH, validate_index
from rag_embed_demo import CACHE_DIR, EXPECTED_DIMENSION, MODEL_NAME
from rag_vector_similarity import cosine_similarity


def load_vector_index() -> dict:
    """读取已经保存的索引；不重新读取原文或计算文档向量。"""
    return json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))


def retrieve_vector_chunks(
    index: dict,
    question: str,
    top_k: int = 2,
) -> list[dict]:
    """仅编码问题，与保存的文档向量逐个比较并返回候选。"""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("问题必须是非空文字。")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k必须是正整数。")

    # 编码前检查索引配置是否与当前模型、维度和编码方式一致。
    validate_index(index)

    model = TextEmbedding(
        model_name=MODEL_NAME,
        cache_dir=str(CACHE_DIR),
        providers=["CPUExecutionProvider"],
        cuda=False,
        threads=2,
    )

    # 列表中只有一个问题，所以本次只生成一个问题向量。
    query_vectors = [
        vector.tolist()
        for vector in model.embed([question.strip()])
    ]
    if len(query_vectors) != 1:
        raise ValueError("问题编码没有返回恰好一个向量。")

    query_vector = query_vectors[0]
    if len(query_vector) != EXPECTED_DIMENSION:
        raise ValueError("问题向量维度不正确。")
    if not all(math.isfinite(value) for value in query_vector):
        raise ValueError("问题向量包含无效数字。")

    results = []
    for chunk in index["chunks"].values():
        # 文档向量来自保存的索引；余弦函数也会拒绝零问题向量。
        score = cosine_similarity(query_vector, chunk["vector"])
        results.append({
            "score": score,
            "content": chunk["content"],
            "metadata": dict(chunk["metadata"]),
        })

    # 高分优先，同分按块编号排序；最多返回top_k个。
    results.sort(
        key=lambda item: (-item["score"], item["metadata"]["chunk_id"])
    )
    return results[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询CampusFlow已保存的文档向量索引"
    )
    parser.add_argument("question", help="需要检索的问题")
    parser.add_argument("--top-k", type=int, default=2, help="最多返回几个候选块")
    args = parser.parse_args()

    try:
        index = load_vector_index()
        results = retrieve_vector_chunks(index, args.question, args.top_k)
    except FileNotFoundError:
        raise SystemExit("检索失败：向量索引不存在，请先构建。")
    except UnicodeDecodeError:
        raise SystemExit("检索失败：索引不是有效的UTF-8文本。")
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"检索失败：{type(error).__name__}：{error}")

    print("本次仅编码问题，文档向量来自已保存索引。")
    print(f"候选块数：{len(results)}")
    print("当前按相似度取Top-K，候选不代表一定包含答案。")

    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        print(f"\n第{rank}名，相似度：{result['score']:.4f}")
        print(f"块编号：{metadata['chunk_id']}")
        print(f"章节：{metadata['section']}")
        print(f"来源：{metadata['source']}")
        print("正文：")
        print(result["content"])


if __name__ == "__main__":
    main()