"""
Comprehensive embedding model comparison test framework.
Compares BAAI/bge-base-en-v1.5 vs sentence-transformers/all-MiniLM-L6-v2 vs other models.
"""

import pytest
import sys
import tempfile
import shutil
import time
import math
from typing import List, Dict, Any, Tuple
from datetime import datetime
import json

# Add AbstractCore path
sys.path.insert(0, '/Users/albou/projects/abstractllm_core')

# Import our embedding infrastructure
from abstractmemory.embeddings.sentence_transformer_provider import (
    SentenceTransformerProvider,
    MODEL_CONFIGS,
    create_sentence_transformer_provider
)
from abstractmemory.embeddings import EmbeddingAdapter

# Try to import sentence-transformers
try:
    import sentence_transformers
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Try to import numpy for similarity calculations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if NUMPY_AVAILABLE:
        # Use numpy for efficiency
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    else:
        # Pure Python implementation
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)


class EmbeddingModelComparator:
    """Class to compare embedding models across various tasks."""

    def __init__(self):
        self.results = {}
        self.models = {}

    def add_model(self, name: str, model_key: str):
        """Add a model to compare."""
        try:
            provider = create_sentence_transformer_provider(model_key)
            adapter = EmbeddingAdapter(provider)
            self.models[name] = {
                'adapter': adapter,
                'provider': provider,
                'config': MODEL_CONFIGS.get(model_key, {'model_name': model_key})
            }
            print(f"✅ Added model: {name} ({model_key})")
        except Exception as e:
            print(f"❌ Failed to add model {name}: {e}")
            self.models[name] = None

    def test_semantic_similarity(self) -> Dict[str, Any]:
        """Test semantic similarity performance."""
        print("\\n🔍 Testing Semantic Similarity...")

        # Test pairs with expected similarity (high, medium, low)
        test_pairs = [
            # High similarity pairs
            ("The cat is sleeping on the couch", "A cat is resting on the sofa", 0.8),
            ("Machine learning is revolutionizing AI", "ML is transforming artificial intelligence", 0.8),
            ("Python is a programming language", "Python is used for software development", 0.7),

            # Medium similarity pairs
            ("I love eating pizza", "Pizza is my favorite food", 0.6),
            ("The weather is sunny today", "It's a beautiful day outside", 0.5),
            ("Dogs are loyal companions", "Cats are independent pets", 0.4),

            # Low similarity pairs
            ("Machine learning algorithms", "Cooking pasta recipes", 0.1),
            ("Financial market analysis", "Playing video games", 0.1),
            ("Quantum physics research", "Gardening techniques", 0.1)
        ]

        results = {}
        for model_name, model_info in self.models.items():
            if model_info is None:
                continue

            adapter = model_info['adapter']
            similarities = []
            errors = []

            print(f"  Testing {model_name}...")

            for text1, text2, expected in test_pairs:
                try:
                    emb1 = adapter.generate_embedding(text1)
                    emb2 = adapter.generate_embedding(text2)
                    similarity = cosine_similarity(emb1, emb2)
                    similarities.append({
                        'text1': text1[:50] + "..." if len(text1) > 50 else text1,
                        'text2': text2[:50] + "..." if len(text2) > 50 else text2,
                        'expected': expected,
                        'actual': similarity,
                        'error': abs(similarity - expected)
                    })
                except Exception as e:
                    errors.append(str(e))

            # Calculate metrics
            if similarities:
                avg_error = sum(s['error'] for s in similarities) / len(similarities)
                max_error = max(s['error'] for s in similarities)
                correlation = self._calculate_correlation(
                    [s['expected'] for s in similarities],
                    [s['actual'] for s in similarities]
                )
            else:
                avg_error = float('inf')
                max_error = float('inf')
                correlation = 0.0

            results[model_name] = {
                'similarities': similarities,
                'avg_error': avg_error,
                'max_error': max_error,
                'correlation': correlation,
                'errors': errors
            }

        return results

    def test_retrieval_performance(self) -> Dict[str, Any]:
        """Test retrieval/search performance."""
        print("\\n🔍 Testing Retrieval Performance...")

        # Document corpus for retrieval testing
        documents = [
            "Python is a high-level programming language known for its simplicity and readability.",
            "Machine learning algorithms can learn patterns from data without explicit programming.",
            "Deep learning uses neural networks with multiple layers to solve complex problems.",
            "Natural language processing enables computers to understand and process human language.",
            "Computer vision allows machines to interpret and analyze visual information from images.",
            "Data science combines statistics, programming, and domain expertise to extract insights.",
            "Artificial intelligence aims to create machines that can perform tasks requiring human intelligence.",
            "Web development involves creating websites and web applications using various technologies.",
            "Database management systems store, organize, and retrieve large amounts of structured data.",
            "Cloud computing provides on-demand access to computing resources over the internet."
        ]

        # Query-document relevance pairs (query, relevant_doc_indices)
        queries = [
            ("programming languages", [0, 7]),  # Python and web dev
            ("artificial intelligence machine learning", [1, 2, 3, 6]),  # ML, deep learning, NLP, AI
            ("data analysis and statistics", [5, 8]),  # Data science, databases
            ("computer graphics and images", [4]),  # Computer vision
            ("internet and online services", [7, 9])  # Web dev, cloud
        ]

        results = {}
        for model_name, model_info in self.models.items():
            if model_info is None:
                continue

            adapter = model_info['adapter']
            print(f"  Testing {model_name}...")

            # Embed all documents
            try:
                doc_embeddings = []
                for doc in documents:
                    emb = adapter.generate_embedding(doc)
                    doc_embeddings.append(emb)

                query_results = []
                for query, relevant_indices in queries:
                    # Embed query
                    query_emb = adapter.generate_embedding(query)

                    # Calculate similarities with all documents
                    doc_similarities = []
                    for i, doc_emb in enumerate(doc_embeddings):
                        sim = cosine_similarity(query_emb, doc_emb)
                        doc_similarities.append((i, sim))

                    # Sort by similarity
                    doc_similarities.sort(key=lambda x: x[1], reverse=True)

                    # Calculate retrieval metrics
                    retrieved_indices = [idx for idx, _ in doc_similarities[:5]]  # Top 5
                    precision_at_5 = len(set(retrieved_indices) & set(relevant_indices)) / min(5, len(relevant_indices))
                    recall_at_5 = len(set(retrieved_indices) & set(relevant_indices)) / len(relevant_indices)

                    query_results.append({
                        'query': query,
                        'relevant_docs': relevant_indices,
                        'retrieved_docs': retrieved_indices,
                        'precision_at_5': precision_at_5,
                        'recall_at_5': recall_at_5,
                        'similarities': doc_similarities[:3]  # Top 3 for inspection
                    })

                # Calculate overall metrics
                avg_precision = sum(r['precision_at_5'] for r in query_results) / len(query_results)
                avg_recall = sum(r['recall_at_5'] for r in query_results) / len(query_results)

                results[model_name] = {
                    'query_results': query_results,
                    'avg_precision_at_5': avg_precision,
                    'avg_recall_at_5': avg_recall,
                    'f1_score': 2 * avg_precision * avg_recall / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
                }

            except Exception as e:
                results[model_name] = {'error': str(e)}

        return results

    def test_performance_metrics(self) -> Dict[str, Any]:
        """Test embedding generation speed and efficiency."""
        print("\\n⚡ Testing Performance Metrics...")

        test_texts = [
            "Short text for speed testing.",
            "This is a medium length text that contains several words and should provide a good baseline for measuring embedding generation performance and efficiency.",
            "This is a much longer text that spans multiple sentences and contains various types of content including technical terms, common words, and more complex linguistic structures. It should help us understand how different models perform with longer input texts and whether there are significant differences in processing time when dealing with more substantial amounts of text content that might be typical in real-world applications."
        ]

        results = {}
        for model_name, model_info in self.models.items():
            if model_info is None:
                continue

            adapter = model_info['adapter']
            print(f"  Testing {model_name} performance...")

            times = {'short': [], 'medium': [], 'long': []}
            text_categories = ['short', 'medium', 'long']

            # Warm up
            try:
                adapter.generate_embedding("warmup")
            except:
                pass

            for category, text in zip(text_categories, test_texts):
                for _ in range(5):  # Average over 5 runs
                    try:
                        start_time = time.time()
                        embedding = adapter.generate_embedding(text)
                        end_time = time.time()

                        times[category].append(end_time - start_time)
                    except Exception as e:
                        print(f"    Error with {category} text: {e}")

            # Calculate average times
            avg_times = {}
            for category in text_categories:
                if times[category]:
                    avg_times[category] = sum(times[category]) / len(times[category])
                else:
                    avg_times[category] = float('inf')

            # Get model info
            model_config = model_info.get('config', {})
            embedding_info = adapter.get_embedding_info()

            results[model_name] = {
                'avg_times': avg_times,
                'dimension': embedding_info.get('dimension', 'unknown'),
                'model_size': model_config.get('parameters', 'unknown'),
                'max_sequence_length': model_config.get('max_sequence_length', 'unknown'),
                'model_info': embedding_info
            }

        return results

    def _calculate_correlation(self, expected: List[float], actual: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(expected) != len(actual) or len(expected) < 2:
            return 0.0

        mean_expected = sum(expected) / len(expected)
        mean_actual = sum(actual) / len(actual)

        numerator = sum((e - mean_expected) * (a - mean_actual) for e, a in zip(expected, actual))

        sum_sq_expected = sum((e - mean_expected) ** 2 for e in expected)
        sum_sq_actual = sum((a - mean_actual) ** 2 for a in actual)

        if sum_sq_expected == 0 or sum_sq_actual == 0:
            return 0.0

        denominator = math.sqrt(sum_sq_expected * sum_sq_actual)
        return numerator / denominator if denominator != 0 else 0.0

    def run_comprehensive_comparison(self) -> Dict[str, Any]:
        """Run all comparison tests."""
        print("🚀 Starting Comprehensive Embedding Model Comparison")
        print("=" * 60)

        start_time = time.time()

        results = {
            'timestamp': datetime.now().isoformat(),
            'models_tested': list(self.models.keys()),
            'semantic_similarity': self.test_semantic_similarity(),
            'retrieval_performance': self.test_retrieval_performance(),
            'performance_metrics': self.test_performance_metrics()
        }

        end_time = time.time()
        results['total_test_time'] = end_time - start_time

        print(f"\\n✅ Comparison completed in {end_time - start_time:.2f} seconds")

        return results


@pytest.mark.skipif(not SENTENCE_TRANSFORMERS_AVAILABLE, reason="sentence-transformers not available")
class TestEmbeddingModelsComparison:
    """Test class for embedding model comparison."""

    def test_bge_vs_minilm_comprehensive_comparison(self):
        """Comprehensive comparison between BGE and MiniLM models."""
        comparator = EmbeddingModelComparator()

        # Add models to compare
        comparator.add_model("BGE-Base-EN-v1.5", "bge-base-en-v1.5")
        comparator.add_model("All-MiniLM-L6-v2", "all-MiniLM-L6-v2")
        comparator.add_model("All-MPNet-Base-v2", "all-mpnet-base-v2")  # Reference model

        # Run comprehensive comparison
        results = comparator.run_comprehensive_comparison()

        # Verify we have results for our models
        assert len(results['semantic_similarity']) > 0
        assert len(results['retrieval_performance']) > 0
        assert len(results['performance_metrics']) > 0

        # Store results for report generation
        self._save_comparison_results(results)

        print("\\n📊 Summary Results:")
        self._print_summary(results)

    def test_individual_model_functionality(self):
        """Test individual model functionality."""
        models_to_test = ["bge-base-en-v1.5", "all-MiniLM-L6-v2"]

        for model_key in models_to_test:
            print(f"\\n🧪 Testing {model_key}...")

            provider = create_sentence_transformer_provider(model_key)
            adapter = EmbeddingAdapter(provider)

            # Test basic embedding generation
            test_text = "This is a test sentence for embedding generation."
            embedding = adapter.generate_embedding(test_text)

            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, (int, float)) for x in embedding)

            # Test consistency
            embedding2 = adapter.generate_embedding(test_text)
            similarity = cosine_similarity(embedding, embedding2)
            assert similarity > 0.99  # Should be nearly identical

            print(f"  ✅ {model_key}: {len(embedding)}D embeddings, consistency: {similarity:.4f}")

    def _save_comparison_results(self, results: Dict[str, Any]):
        """Save results to temp file for report generation."""
        temp_dir = tempfile.gettempdir()
        results_file = f"{temp_dir}/embedding_comparison_results.json"

        # Convert numpy floats to regular floats for JSON serialization
        def convert_floats(obj):
            if isinstance(obj, dict):
                return {k: convert_floats(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats(v) for v in obj]
            elif hasattr(obj, 'item'):  # numpy scalars
                return obj.item()
            return obj

        try:
            results_clean = convert_floats(results)
            with open(results_file, 'w') as f:
                json.dump(results_clean, f, indent=2)
            print(f"\\n💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"\\n⚠️ Could not save results: {e}")

    def _print_summary(self, results: Dict[str, Any]):
        """Print a summary of comparison results."""
        print("\\n" + "="*60)
        print("📈 EMBEDDING MODEL COMPARISON SUMMARY")
        print("="*60)

        # Semantic similarity summary
        if 'semantic_similarity' in results:
            print("\\n🎯 Semantic Similarity Performance:")
            for model, data in results['semantic_similarity'].items():
                if 'avg_error' in data:
                    print(f"  {model}: Avg Error = {data['avg_error']:.3f}, Correlation = {data.get('correlation', 0):.3f}")

        # Retrieval performance summary
        if 'retrieval_performance' in results:
            print("\\n🔍 Retrieval Performance:")
            for model, data in results['retrieval_performance'].items():
                if 'avg_precision_at_5' in data:
                    print(f"  {model}: P@5 = {data['avg_precision_at_5']:.3f}, R@5 = {data['avg_recall_at_5']:.3f}, F1 = {data['f1_score']:.3f}")

        # Performance metrics summary
        if 'performance_metrics' in results:
            print("\\n⚡ Performance Metrics:")
            for model, data in results['performance_metrics'].items():
                if 'avg_times' in data:
                    avg_time = data['avg_times'].get('medium', 0)
                    dimension = data.get('dimension', 'unknown')
                    size = data.get('model_size', 'unknown')
                    print(f"  {model}: {avg_time*1000:.1f}ms/embedding, {dimension}D, {size} params")


if __name__ == "__main__":
    # Allow running this test directly
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        comparator = EmbeddingModelComparator()
        comparator.add_model("BGE-Base-EN-v1.5", "bge-base-en-v1.5")
        comparator.add_model("All-MiniLM-L6-v2", "all-MiniLM-L6-v2")
        results = comparator.run_comprehensive_comparison()
        print("\\n🎉 Direct test run completed!")
    else:
        print("❌ sentence-transformers not available for direct testing")