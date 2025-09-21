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
        "lancedb>=0.3.0",       # For vector storage
        "sentence-transformers>=2.0.0",  # For embeddings
        "pydantic>=2.0.0",      # For data validation
    ],
    extras_require={
        "dev": ["pytest", "black", "mypy"],
    }
)