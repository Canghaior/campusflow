import json
import math
from importlib.metadata import version

from fastembed import TextEmbedding

from rag_chunk_document import split_document
from rag_embed_demo import (
    CACHE_DIR,
    EXPECTED_DIMENSION,
    MODEL_NAME,
    PROJECT_DIR,
)
from rag_load_document import DEFAULT_SOURCE, load_document


INDEX_PATH = PROJECT_DIR / "data" / "index" / "vector_index.json"


def embedding_config() -> dict:
    """记录本次文档向量使用的编码配置。"""
    return {
        "model_name": MODEL_NAME,
        "dimension": EXPECTED_DIMENSION,
        "fastembed_version": version("fastembed"),
        "input_mode": "raw_text",
        "similarity": "cosine",
    }


def validate_index(index: dict) -> None:
    """检查配置，以及每个块的正文、来源和向量。"""
    if not isinstance(index, dict):
        raise ValueError("索引必须是字典。")

    if (
        index.get("schema_version") != 1
        or index.get("index_type") != "dense_vector_flat"
    ):
        raise ValueError("索引格式不匹配。")

    if index.get("embedding") != embedding_config():
        raise ValueError("索引编码配置与当前程序不一致。")

    chunks = index.get("chunks")
    if not isinstance(chunks, dict) or not chunks:
        raise ValueError("索引必须包含文档块。")

    for chunk_id, chunk in chunks.items():
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("块编号无效。")
        if not isinstance(chunk, dict):
            raise ValueError("块数据格式无效。")

        content = chunk.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("块正文不能为空。")

        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("缺少来源信息。")

        for field in ["source", "filename", "section", "chunk_id"]:
            value = metadata.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"来源字段 {field} 不完整。")

        if metadata["chunk_id"] != chunk_id:
            raise ValueError("块编号与元数据中的编号不一致。")

        vector = chunk.get("vector")
        if not isinstance(vector, list) or len(vector) != EXPECTED_DIMENSION:
            raise ValueError("向量维度不正确。")

        # 拒绝布尔值、非数字、无穷大和NaN。
        if not all(
            type(value) in (int, float) and math.isfinite(value)
            for value in vector
        ):
            raise ValueError("向量必须由有限数字组成。")

        if not any(value != 0 for value in vector):
            raise ValueError("不能保存零向量。")


def main() -> None:
    try:
        document = load_document(DEFAULT_SOURCE)
        chunks = split_document(document)
        if not chunks:
            raise ValueError("没有可以建立索引的文档块。")

        print("正在计算文档向量……")
        model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(CACHE_DIR),
            providers=["CPUExecutionProvider"],
            cuda=False,
            threads=2,
        )

        # 本次只编码文档块，不把某个用户问题存入文档索引。
        texts = [chunk["content"] for chunk in chunks]
        vectors = [vector.tolist() for vector in model.embed(texts)]

        if len(vectors) != len(chunks):
            raise ValueError("文档块数量与向量数量不一致。")

        records = {}
        for chunk, vector in zip(chunks, vectors):
            chunk_id = chunk["metadata"]["chunk_id"]
            if chunk_id in records:
                raise ValueError(f"块编号重复：{chunk_id}")

            # 同一个记录绑定向量、原文和来源，避免排序后对应错位。
            records[chunk_id] = {
                "content": chunk["content"],
                "metadata": dict(chunk["metadata"]),
                "vector": vector,
            }

        index = {
            "schema_version": 1,
            "index_type": "dense_vector_flat",
            "embedding": embedding_config(),
            "chunks": records,
        }
        validate_index(index)

        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 先完整写入临时文件，再替换目标，减少写到一半损坏旧索引的风险。
        temporary_path = INDEX_PATH.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(
                index,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(INDEX_PATH)

        # 读回实际保存的文件，再次检查数据结构与编码配置。
        saved = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        validate_index(saved)
        if saved != index:
            raise ValueError("读回内容与构建内容不一致。")

    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"构建失败：{type(error).__name__}：{error}")

    print(f"\n已保存：{INDEX_PATH}")
    print(f"读回块数：{len(saved['chunks'])}")
    print(f"模型：{saved['embedding']['model_name']}")
    print(f"FastEmbed版本：{saved['embedding']['fastembed_version']}")
    print("配置、正文、来源和向量检查通过。")

    for chunk_id, chunk in saved["chunks"].items():
        print(f"\n块编号：{chunk_id}")
        print(f"向量维度：{len(chunk['vector'])}")
        print(f"章节：{chunk['metadata']['section']}")
        print(f"来源：{chunk['metadata']['source']}")


if __name__ == "__main__":
    main()