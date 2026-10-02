import asyncio

from layer_api.integrations import gmail, jira, notion
from layer_api.agent.nodes.search import rerank_and_grade


def test_gmail_search_keeps_saved_filter():
    class Tools:
        async def call(self, name, arguments):
            assert name == "GMAIL_FETCH_EMAILS"
            assert arguments["query"].startswith("label:phoenix")
            assert "deadline" in arguments["query"]
            return {"messages": [{"messageId": "m1", "subject": "Deadline", "sender": "team@example.com", "body": "Moved to November"}]}

    found = asyncio.run(gmail.evidence(Tools(), {"labels": ["phoenix"], "senders": [], "keywords": [], "query": "label:phoenix"}, "deadline"))
    assert found[0]["id"] == "gmail:m1"
    assert "Moved to November" in found[0]["text"]


def test_jira_search_keeps_project_and_saved_jql():
    class Tools:
        async def call(self, name, arguments):
            if name == "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST":
                assert arguments["jql"].startswith('project = "PHX" AND (status = Open) AND text ~ "blocker"')
                return {"issues": [{"key": "PHX-1"}]}
            assert name == "JIRA_GET_ISSUE" and arguments["issue_id_or_key"] == "PHX-1"
            return {"browser_url": "https://jira.example/browse/PHX-1", "fields": {
                "project": {"name": "Phoenix"}, "summary": "Fix launch", "status": {"name": "Open"},
                "assignee": {"displayName": "Sam"}, "comment": {"comments": [{"body": "Ready soon"}]},
            }}

    found = asyncio.run(jira.evidence(Tools(), {"project_key": "PHX", "jql": "status = Open"}, "blocker"))
    assert found[0]["id"] == "jira:PHX-1"
    assert "Phoenix" in found[0]["text"] and "Ready soon" in found[0]["text"]


def test_notion_reads_selected_page_and_its_child_only():
    called = []

    class Tools:
        async def call(self, name, arguments):
            called.append((name, arguments))
            if name == "NOTION_RETRIEVE_PAGE":
                page_id = arguments["page_id"]
                return {"object": "page", "properties": {"title": {"type": "title", "title": [{"plain_text": page_id}]}},
                        "url": f"https://www.notion.so/{page_id}"}
            if name == "NOTION_GET_PAGE_MARKDOWN":
                return {"markdown": f'# {arguments["page_id"]}\n\nProject plan'}
            if name == "NOTION_FETCH_BLOCK_CONTENTS":
                return {"results": [{"type": "child_page", "id": "child"}]} if arguments["block_id"] == "selected" else {"results": []}
            raise AssertionError(name)

    found = asyncio.run(notion.evidence(Tools(), {"page_ids": ["selected"], "database_ids": []}, "plan"))
    assert {item["id"].split(":")[1] for item in found} == {"selected", "child"}
    assert {item["title"] for item in found} == {"selected", "child"}
    assert all("unselected" not in str(arguments) for _, arguments in called)


def test_notion_skips_empty_page_placeholder():
    class Tools:
        async def call(self, name, arguments):
            if name == "NOTION_RETRIEVE_PAGE":
                return {"object": "page", "properties": {"title": {"type": "title", "title": [{"plain_text": "Empty"}]}}}
            if name == "NOTION_GET_PAGE_MARKDOWN":
                return {"markdown": "<empty-block/>"}
            return {"results": []}

    found = asyncio.run(notion.evidence(Tools(), {"page_ids": ["empty"], "database_ids": []}, ""))
    assert found == []


def test_rerank_keeps_top_results_with_negative_cross_encoder_scores():
    class Engine:
        async def rerank(self, query, passages, top_k=5):
            return {"result": [{**passages[0], "score": -11.4}]}

    evidence = {"id": "jira:KAN-1", "source_type": "jira", "title": "Task", "text": "Phoenix task",
                "url": None, "date": None, "step_index": 0, "score": None}
    state = {"plan": [{"source": "jira", "sub_question": "What is the task?", "search_terms": ""}],
             "evidence": [evidence]}
    result = asyncio.run(rerank_and_grade(state, Engine()))
    assert result["evidence"].value[0]["id"] == "jira:KAN-1"
    assert result["insufficient_context"] is False
