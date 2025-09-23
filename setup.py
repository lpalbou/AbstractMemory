from setuptools import setup, find_packages

setup(
    name="abstractmemory",
    version="1.0.0",
    author="AbstractLLM Team",
    description="Temporal knowledge graph memory system for LLM agents",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "networkx>=3.0",        # For graph operations
    ],
    extras_require={
        "dev": ["pytest", "black", "mypy"],
        "llm": ["abstractllm>=0.5.0"],  # For real LLM integration tests
    }
)