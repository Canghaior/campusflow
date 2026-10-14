import math


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个非零数值向量的余弦相似度。"""
    if not left or not right:
        raise ValueError("向量不能为空。")

    # 维度就是向量里数字的个数，必须一致才能逐项相乘。
    if len(left) != len(right):
        raise ValueError("两个向量的维度必须一致。")

    # 点积：对应位置相乘，再求和。
    dot_product = sum(a * b for a, b in zip(left, right))

    # 模长：各分量平方后求和，再开平方。
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        raise ValueError("零向量没有方向，不能计算余弦相似度。")

    return dot_product / (left_norm * right_norm)


def main() -> None:
    # 全部是人工设置的教学向量，不是模型生成的文本 Embedding。
    query = [1.0, 0.0]
    candidates = [
        {"id": "A", "vector": [1.0, 1.0]},
        {"id": "B", "vector": [4.0, 0.0]},
        {"id": "C", "vector": [0.0, 1.0]},
    ]

    results = []
    for candidate in candidates:
        score = cosine_similarity(query, candidate["vector"])
        results.append({
            "id": candidate["id"],
            "vector": candidate["vector"],
            "score": score,
        })

    # 分数从高到低；同分时按编号排序。
    results.sort(key=lambda item: (-item["score"], item["id"]))

    print("人工向量演示，不代表真实文本检索效果。")
    print(f"查询向量：{query}")

    print("\n候选排序：")
    for result in results:
        print(
            f"{result['id']}：向量={result['vector']}，"
            f"相似度={result['score']:.4f}"
        )

    top_k = 2
    selected_ids = [item["id"] for item in results[:top_k]]
    print(f"\nTop-{top_k}：{'、'.join(selected_ids)}")

    # 比较方向相同、长度不同的两个向量。
    original_score = cosine_similarity(query, [4.0, 0.0])
    scaled_score = cosine_similarity(query, [40.0, 0.0])
    print(f"\nB原始分数：{original_score:.4f}")
    print(f"B放大10倍后的分数：{scaled_score:.4f}")

    # 单独验证零向量边界，捕获预期错误后正常结束。
    print("\n零向量检查：")
    try:
        cosine_similarity(query, [0.0, 0.0])
    except ValueError as error:
        print(f"已拒绝：{error}")
    else:
        raise AssertionError("零向量应当被拒绝，请检查实现。")


if __name__ == "__main__":
    main()