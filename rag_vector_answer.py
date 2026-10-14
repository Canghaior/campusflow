import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

# 复用已有回答请求和引用编号检查，不复制其内部实现。
from rag_answer import request_answer, check_citation_ids
from rag_prepare_answer import build_answer_messages
from rag_vector_retrieve import load_vector_index, retrieve_vector_chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CampusFlow向量检索与来源引用问答"
    )
    parser.add_argument("question", help="需要回答的问题")
    parser.add_argument("--top-k", type=int, default=2, help="最多提供几个候选块")
    args = parser.parse_args()

    try:
        index = load_vector_index()
        results = retrieve_vector_chunks(index, args.question, args.top_k)

        # 候选中的正文和来源，沿用已有的消息组装方式。
        messages = build_answer_messages(args.question, results)
    except FileNotFoundError:
        raise SystemExit("准备失败：向量索引不存在，请先构建。")
    except UnicodeDecodeError:
        raise SystemExit("准备失败：索引不是有效的UTF-8文本。")
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"准备失败：{type(error).__name__}：{error}")

    # 保留空候选处理；当前非空索引无分数过滤时，通常会有候选。
    if not messages:
        print("未检索到候选片段，当前资料无法确认这个问题。")
        print("本次未调用回答模型。")
        return

    # 从实际发送的消息读取S编号对应关系，避免重新编号。
    evidence = json.loads(messages[1]["content"])["evidence"]

    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "replace_with_your_api_key":
        raise SystemExit("配置错误：项目尚未配置有效的LLM_API_KEY。")

    print(f"向量检索候选数：{len(results)}")
    print("候选存在不代表依据充分，回答仍需对照正文核验。")

    try:
        with OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0,
            max_retries=0,
        ) as client:
            print("正在发起一次回答模型请求……")
            answer = request_answer(client, messages)

        used = check_citation_ids(answer, evidence)
    except APITimeoutError:
        raise SystemExit("请求超时：没有自动重试。")
    except APIConnectionError:
        raise SystemExit("连接失败：请检查网络或代理设置。")
    except APIStatusError as error:
        raise SystemExit(f"服务返回错误：HTTP {error.status_code}。")
    except ValueError as error:
        raise SystemExit(f"回答检查失败：{error}")

    print("\n模型回答：")
    print(answer)

    if used:
        print("\n引用编号检查通过；仍需检查原文是否支持结论。")
    else:
        print("\n未检测到标准[S编号]引用。")
        print("若回答仅说明无法确认，可以没有引用；")
        print("若包含确定的规则事实，需要检查是否遗漏引用。")

    # 显示本次提供了哪些资料，并区分是否被回答实际引用。
    score_by_id = {
        result["metadata"]["chunk_id"]: result["score"]
        for result in results
    }

    print("\n本次证据来源：")
    for item in evidence:
        label = f"[{item['citation_id']}]"
        state = "回答已引用" if label in used else "仅提供为候选"
        score = score_by_id[item["chunk_id"]]

        print(f"\n{label} {item['filename']}，{item['section']}")
        print(f"引用状态：{state}")
        print(f"检索相似度：{score:.4f}")
        print(f"来源路径：{item['source']}")
        print(f"块编号：{item['chunk_id']}")


if __name__ == "__main__":
    main()