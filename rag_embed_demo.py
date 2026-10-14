import math
from importlib.metadata import version
from pathlib import Path

from fastembed import TextEmbedding

from rag_chunk_document import split_document
from rag_load_document import DEFAULT_SOURCE, load_document
from rag_vector_similarity import cosine_similarity


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EXPECTED_DIMENSION = 512
QUESTION = "退课由谁审查？"

# 模型文件放在虚拟环境目录中，便于复用下载缓存。
PROJECT_DIR = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_DIR / ".venv" / "model_cache"


def main() -> None:
    print(f"FastEmbed版本：{version('fastembed')}")
    print(f"模型：{MODEL_NAME}")
    print(f"模型缓存目录：{CACHE_DIR}")

    try:
        # 读取现有模拟资料，并保留每一块的正文和来源信息。
        document = load_document(DEFAULT_SOURCE)
        chunks = split_document(document)

        if not chunks:
            raise ValueError("没有可编码的文档块。")

        print(f"\n问题：{QUESTION}")
        print(f"文档块数：{len(chunks)}")
        print("正在加载模型；首次运行可能需要下载模型文件……")

        model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(CACHE_DIR),
            providers=["CPUExecutionProvider"],
            cuda=False,
            threads=2,
        )

        # 第0项是问题，后面的项按顺序对应各个文档块。
        # 这次用同一个模型直接编码短问题和短条款。
        texts = [QUESTION] + [chunk["content"] for chunk in chunks]

        # embed逐个产生向量；tolist将数组转换成普通Python列表，
        # 以便复用上一小步的cosine_similarity函数。
        vectors = [
            vector.tolist()
            for vector in model.embed(texts)
        ]

        if len(vectors) != len(texts):
            raise ValueError("返回的向量数量与输入文本数量不一致。")

        for vector in vectors:
            if len(vector) != EXPECTED_DIMENSION:
                raise ValueError("模型返回了非预期维度的向量。")
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("向量中存在无穷大或非数值结果。")

        query_vector = vectors[0]
        document_vectors = vectors[1:]

        results = []
        for chunk, vector in zip(chunks, document_vectors):
            # 复用已有函数；如果出现零向量，该函数会明确拒绝。
            score = cosine_similarity(query_vector, vector)
            results.append({
                "score": score,
                "content": chunk["content"],
                "metadata": dict(chunk["metadata"]),
            })

        results.sort(
            key=lambda item: (
                -item["score"],
                item["metadata"]["chunk_id"],
            )
        )

    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"向量演示失败：{type(error).__name__}：{error}")

    print(
        f"\n向量检查通过：共{len(vectors)}个，"
        f"均为{EXPECTED_DIMENSION}维、数值有限且非零。"
    )
    print("问题向量前5个数：")
    print([round(value, 6) for value in query_vector[:5]])

    print("\n实际候选排序：")
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        print(f"\n第{rank}名，相似度：{result['score']:.4f}")
        print(f"章节：{metadata['section']}")
        print(f"来源：{metadata['source']}")
        print(f"块编号：{metadata['chunk_id']}")

    print("\n本次只计算向量和候选排序，尚未生成问答结果。")


if __name__ == "__main__":
    main()