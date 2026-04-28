.PHONY: setup run eval clean

setup:
	uv sync

run:
	uv run streamlit run app.py

eval:
	uv run pytest evals/test_agent.py -v --tb=short

clean:
	rm -rf __pycache__ .pytest_cache .venv
