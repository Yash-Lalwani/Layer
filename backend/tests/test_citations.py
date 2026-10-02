from layer_api.agent.citations import checked_answer, citation_request, parse_statements


def test_parses_numbered_statements_and_passage_ids():
    statements = parse_statements("Launch is in November [2].\nThe plan is approved [1] [2].")
    assert statements == [
        {"text": "Launch is in November.", "citation_numbers": [2]},
        {"text": "The plan is approved.", "citation_numbers": [1, 2]},
    ]
    evidence = [
        {"id": "a", "source_type": "drive", "title": "A", "text": "one", "url": None, "date": None, "step_index": 0, "score": 1.0},
        {"id": "b", "source_type": "gmail", "title": "B", "text": "two", "url": None, "date": None, "step_index": 1, "score": 1.0},
    ]
    claims, passages = citation_request(statements, evidence)
    assert claims[0]["chunk_ids"] == ["b"]
    assert passages[1] == {"id": "b", "text": "two"}


def test_unsupported_statement_removed_and_sources_renumbered():
    evidence = [
        {"id": "a", "source_type": "drive", "title": "A", "text": "one", "url": None, "date": None, "step_index": 0, "score": 1.0},
        {"id": "b", "source_type": "gmail", "title": "B", "text": "two", "url": None, "date": None, "step_index": 1, "score": 1.0},
    ]
    statements = parse_statements("Unsupported claim [1].\nSupported claim [2].")
    text, final_statements, sources, verification = checked_answer(statements, evidence, [
        {"index": 0, "supported": False}, {"index": 1, "supported": True},
    ])
    assert text == "Supported claim. [1]"
    assert final_statements == [{"text": "Supported claim.", "citation_numbers": [1]}]
    assert sources[0]["title"] == "B"
    assert verification == {"checked": 2, "supported": 1, "removed": 1, "succeeded": True}
