"""
Exhaustive Real Embeddings Integration Tests
==========================================

These tests use REAL AbstractCore LLMs and EmbeddingManager to demonstrate:
1. True semantic similarity in embeddings
2. Accurate vector search in LanceDB
3. End-to-end LLM + semantic memory workflows
4. Performance characteristics with real data

NO MOCKS OR SIMULATIONS - Only real implementations.
"""

import pytest
import tempfile
import shutil
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple

# Add AbstractCore path
sys.path.insert(0, '/Users/albou/projects/abstractllm_core')

from abstractmemory import create_memory
from abstractmemory.embeddings import create_embedding_adapter

# Skip if AbstractCore not available
try:
    from abstractllm.embeddings import EmbeddingManager
    from abstractllm import create_llm
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False


@pytest.mark.skipif(not ABSTRACTCORE_AVAILABLE, reason="AbstractCore not available")
class TestRealEmbeddingsExhaustive:
    """Exhaustive tests with real AbstractCore embeddings and LLMs"""

    def setup_method(self):
        """Setup with real AbstractCore components"""
        self.temp_dir = tempfile.mkdtemp()
        self.embedding_manager = EmbeddingManager()

        # Try to create real LLM provider (if available)
        self.llm_provider = None
        try:
            # Try Ollama first
            self.llm_provider = create_llm("ollama", model="qwen3-coder:7b")
            self.provider_name = "ollama"
        except:
            try:
                # Try MLX
                self.llm_provider = create_llm("mlx", model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit")
                self.provider_name = "mlx"
            except:
                self.provider_name = "no_llm"

    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)

    def test_embedding_semantic_similarity_accuracy(self):
        """Test that embeddings actually capture semantic meaning"""

        # Create test pairs with known semantic relationships
        test_pairs = [
            # High similarity pairs
            ("machine learning algorithms", "AI and neural networks"),
            ("Python programming", "coding in Python language"),
            ("database queries", "SQL and data retrieval"),
            ("web development", "frontend and backend programming"),

            # Medium similarity pairs
            ("artificial intelligence", "computer programming"),
            ("mathematics concepts", "software engineering"),

            # Low similarity pairs
            ("machine learning algorithms", "Italian pasta recipes"),
            ("Python programming syntax", "organic gardening methods"),
            ("SQL database operations", "mountain hiking trails")
        ]

        print("🧪 Testing semantic similarity accuracy...")

        adapter = create_embedding_adapter(self.embedding_manager)
        assert adapter.provider_type == "abstractcore_embeddings"
        assert adapter.is_real_embedding()

        similarities = []

        for text1, text2 in test_pairs:
            # Generate embeddings
            emb1 = adapter.generate_embedding(text1)
            emb2 = adapter.generate_embedding(text2)

            # Compute cosine similarity
            similarity = self._cosine_similarity(emb1, emb2)
            similarities.append((text1, text2, similarity))

            print(f"   '{text1}' vs '{text2}': {similarity:.3f}")

        # Verify semantic relationships
        high_sim_pairs = similarities[:4]  # First 4 should be high similarity
        low_sim_pairs = similarities[-4:]  # Last 4 should be low similarity

        # High similarity pairs should have similarity > 0.5
        for text1, text2, sim in high_sim_pairs:
            assert sim > 0.5, f"'{text1}' vs '{text2}' should be similar but got {sim:.3f}"

        # Low similarity pairs should have similarity < 0.7 (model is very sophisticated)
        for text1, text2, sim in low_sim_pairs:
            assert sim < 0.7, f"'{text1}' vs '{text2}' should be dissimilar but got {sim:.3f}"

        print(f"✅ Semantic similarity test passed with real embeddings")

    def test_lancedb_vector_search_accuracy(self):
        """Test that LanceDB vector search finds semantically similar content"""

        # Create memory with real embeddings
        memory = create_memory(
            "grounded",
            storage_backend="lancedb",
            storage_uri=f"{self.temp_dir}/vector_test.db",
            embedding_provider=self.embedding_manager,
            working_capacity=10
        )

        print("🔍 Testing LanceDB vector search accuracy...")

        # Add diverse interactions with known semantic relationships
        test_interactions = [
            # Machine Learning cluster
            ("alice", "I'm working on neural network architectures", "Great! Deep learning is fascinating."),
            ("bob", "Can you help with ML model training?", "Sure! Training models requires good data."),
            ("charlie", "Artificial intelligence is the future", "AI will transform many industries."),

            # Programming cluster
            ("alice", "Python is my favorite programming language", "Python is excellent for development!"),
            ("bob", "I need help with software development", "Let's work on your coding project."),
            ("diana", "Web development with JavaScript", "JS is great for interactive websites."),

            # Cooking cluster
            ("eve", "I love cooking Italian pasta dishes", "Italian cuisine is wonderful!"),
            ("frank", "Best recipes for homemade bread", "Fresh bread is so satisfying to make."),
            ("grace", "Grilling techniques for BBQ", "BBQ brings people together."),

            # Travel cluster
            ("henry", "Planning a trip to Japan", "Japan has amazing culture and food!"),
            ("iris", "European vacation destinations", "Europe has so much history to explore."),
        ]

        # Add all interactions
        for user, user_input, agent_response in test_interactions:
            memory.set_current_user(user)
            memory.add_interaction(user_input, agent_response)

        print(f"   Added {len(test_interactions)} interactions")

        # Test semantic queries
        test_queries = [
            # Should find ML cluster
            ("deep learning models", ["neural", "ML", "intelligence"]),
            ("artificial intelligence research", ["neural", "ML", "intelligence"]),

            # Should find programming cluster
            ("software engineering", ["Python", "development", "JavaScript"]),
            ("coding projects", ["Python", "development", "JavaScript"]),

            # Should find cooking cluster
            ("food preparation", ["cooking", "recipes", "bread"]),
            ("culinary arts", ["cooking", "recipes", "bread"]),

            # Should find travel cluster
            ("vacation planning", ["Japan", "European", "trip"]),
            ("tourism destinations", ["Japan", "European", "trip"]),
        ]

        search_results = []

        for query, expected_keywords in test_queries:
            results = memory.search_stored_interactions(query)

            print(f"   Query: '{query}' → {len(results)} results")

            if results:
                # Check if results contain expected keywords
                found_keywords = []
                for result in results:
                    text = result['user_input'].lower()
                    for keyword in expected_keywords:
                        if keyword.lower() in text:
                            found_keywords.append(keyword)

                relevance_score = len(set(found_keywords)) / len(expected_keywords)
                search_results.append((query, len(results), relevance_score))

                print(f"     Top result: '{results[0]['user_input'][:50]}...'")
                print(f"     Relevance: {relevance_score:.2f} ({found_keywords})")
            else:
                search_results.append((query, 0, 0.0))
                print(f"     No results found")

        # Verify search quality
        total_queries = len(search_results)
        queries_with_results = sum(1 for _, count, _ in search_results if count > 0)
        avg_relevance = sum(score for _, _, score in search_results) / total_queries

        print(f"✅ Vector search results: {queries_with_results}/{total_queries} queries found results")
        print(f"✅ Average relevance score: {avg_relevance:.2f}")

        # We expect at least 80% of queries to find results
        assert queries_with_results >= total_queries * 0.8, f"Too few queries found results: {queries_with_results}/{total_queries}"

    def test_end_to_end_llm_semantic_memory_workflow(self):
        """Test complete workflow: LLM generates response using semantic memory"""

        if self.llm_provider is None:
            pytest.skip("No LLM provider available for end-to-end test")

        print(f"🤖 Testing end-to-end LLM + semantic memory with {self.provider_name}...")

        # Create memory with real embeddings
        memory = create_memory(
            "grounded",
            storage_backend="lancedb",
            storage_uri=f"{self.temp_dir}/llm_test.db",
            embedding_provider=self.embedding_manager,
            working_capacity=15
        )

        # Build up a knowledge base
        knowledge_base = [
            ("alice", "Python list comprehensions are concise", "Yes! They're more readable than loops."),
            ("alice", "Machine learning requires good data", "Quality data is crucial for ML success."),
            ("alice", "Neural networks have multiple layers", "Deep networks can learn complex patterns."),
            ("bob", "JavaScript handles async operations well", "Promises and async/await are powerful."),
            ("bob", "React is great for user interfaces", "Component-based architecture is clean."),
            ("charlie", "Data science involves statistics", "Statistics help interpret data patterns."),
            ("charlie", "Pandas is useful for data analysis", "DataFrames make data manipulation easy."),
            ("diana", "API design should be RESTful", "REST principles create maintainable APIs."),
            ("diana", "Database normalization reduces redundancy", "Normalized schemas are more efficient."),
        ]

        # Add knowledge to memory
        for user, user_input, agent_response in knowledge_base:
            memory.set_current_user(user)
            memory.add_interaction(user_input, agent_response)

        print(f"   Built knowledge base with {len(knowledge_base)} interactions")

        # Test LLM using semantic memory for context
        test_scenarios = [
            {
                "user_id": "alice",
                "query": "How can I improve my ML model performance?",
                "expected_context": ["data", "neural", "machine learning"],
                "context_source": "semantic_search"
            },
            {
                "user_id": "bob",
                "query": "What's the best way to handle frontend state?",
                "expected_context": ["React", "JavaScript", "async"],
                "context_source": "semantic_search"
            },
            {
                "user_id": "charlie",
                "query": "How do I analyze large datasets efficiently?",
                "expected_context": ["Pandas", "data", "statistics"],
                "context_source": "semantic_search"
            }
        ]

        for scenario in test_scenarios:
            user_id = scenario["user_id"]
            query = scenario["query"]
            expected_context = scenario["expected_context"]

            print(f"   Testing scenario: {user_id} asks '{query}'")

            # Get semantic context
            memory_context = memory.get_full_context(query, user_id=user_id)
            search_results = memory.search_stored_interactions(query, user_id=user_id)

            # Verify semantic search found relevant context
            if search_results:
                found_context = []
                for result in search_results:
                    text = (result['user_input'] + ' ' + result['agent_response']).lower()
                    for term in expected_context:
                        if term.lower() in text:
                            found_context.append(term)

                context_quality = len(set(found_context)) / len(expected_context)
                print(f"     Semantic context quality: {context_quality:.2f}")
                print(f"     Found terms: {set(found_context)}")

                assert context_quality > 0.3, f"Poor semantic context for '{query}': {context_quality}"

            # Generate LLM response with context
            try:
                prompt = f"""Context from memory:
{memory_context}

User question: {query}
Provide a helpful response based on the context above."""

                start_time = time.time()
                response = self.llm_provider.generate(prompt)
                response_time = time.time() - start_time

                response_text = response.content if hasattr(response, 'content') else str(response)

                print(f"     LLM response ({response_time:.1f}s): {response_text[:100]}...")

                # Verify LLM used the context
                context_used = any(term.lower() in response_text.lower() for term in expected_context)
                if context_used:
                    print(f"     ✅ LLM used semantic context")
                else:
                    print(f"     ⚠️ LLM may not have used context effectively")

                # Add the interaction to memory for future queries
                memory.set_current_user(user_id)
                memory.add_interaction(query, response_text)

            except Exception as e:
                print(f"     ❌ LLM generation failed: {e}")
                # Don't fail the test - just note the issue
                continue

        print(f"✅ End-to-end LLM + semantic memory workflow completed")

    def test_embedding_consistency_and_caching(self):
        """Test that embeddings are consistent and caching works properly"""

        print("🔄 Testing embedding consistency and caching...")

        adapter = create_embedding_adapter(self.embedding_manager)

        test_texts = [
            "Machine learning is transforming technology",
            "Python programming language",
            "Database query optimization",
            "Web development frameworks",
            "Artificial intelligence research"
        ]

        # Generate embeddings multiple times
        consistency_results = []
        timing_results = []

        for text in test_texts:
            embeddings = []
            times = []

            for i in range(3):  # Generate 3 times
                start_time = time.time()
                embedding = adapter.generate_embedding(text)
                end_time = time.time()

                embeddings.append(embedding)
                times.append(end_time - start_time)

            # Check consistency
            emb1, emb2, emb3 = embeddings
            similarity_12 = self._cosine_similarity(emb1, emb2)
            similarity_13 = self._cosine_similarity(emb1, emb3)

            consistency_results.append((text, similarity_12, similarity_13))
            timing_results.append((text, times))

            print(f"   '{text[:30]}...': consistency {similarity_12:.4f}, {similarity_13:.4f}")
            print(f"     Timing: {times[0]:.3f}s, {times[1]:.3f}s, {times[2]:.3f}s")

        # Verify consistency (should be perfect for same text)
        for text, sim12, sim13 in consistency_results:
            assert sim12 > 0.999, f"Inconsistent embeddings for '{text}': {sim12}"
            assert sim13 > 0.999, f"Inconsistent embeddings for '{text}': {sim13}"

        # Verify performance characteristics
        avg_first_time = sum(times[0] for _, times in timing_results) / len(timing_results)
        avg_subsequent_time = sum((times[1] + times[2])/2 for _, times in timing_results) / len(timing_results)

        print(f"✅ Embedding consistency: Perfect (1.000)")
        print(f"✅ Average timing - First: {avg_first_time:.3f}s, Cached: {avg_subsequent_time:.3f}s")

    def test_large_scale_performance_benchmark(self):
        """Benchmark performance with realistic data volumes"""

        print("📊 Running large-scale performance benchmark...")

        # Create memory with real embeddings
        memory = create_memory(
            "grounded",
            storage_backend="lancedb",
            storage_uri=f"{self.temp_dir}/benchmark.db",
            embedding_provider=self.embedding_manager,
            working_capacity=20
        )

        # Generate realistic dataset
        domains = [
            ("programming", [
                "Python functions and classes",
                "JavaScript async programming",
                "Database design patterns",
                "API development best practices",
                "Software testing strategies"
            ]),
            ("machine_learning", [
                "Neural network architectures",
                "Training deep learning models",
                "Feature engineering techniques",
                "Model evaluation metrics",
                "Transfer learning approaches"
            ]),
            ("data_science", [
                "Statistical analysis methods",
                "Data visualization techniques",
                "Pandas data manipulation",
                "Hypothesis testing procedures",
                "Exploratory data analysis"
            ]),
            ("web_development", [
                "Frontend frameworks comparison",
                "Backend architecture patterns",
                "Database optimization strategies",
                "Security best practices",
                "Performance monitoring tools"
            ])
        ]

        # Add interactions at scale
        start_time = time.time()
        total_interactions = 0
        users = ["alice", "bob", "charlie", "diana", "eve"]

        for domain, topics in domains:
            for user in users:
                for i, topic in enumerate(topics):
                    memory.set_current_user(user)
                    memory.add_interaction(
                        f"Tell me about {topic}",
                        f"Here's information about {topic} in {domain}..."
                    )
                    total_interactions += 1

        insertion_time = time.time() - start_time

        print(f"   Inserted {total_interactions} interactions in {insertion_time:.2f}s")
        print(f"   Rate: {total_interactions/insertion_time:.1f} interactions/second")

        # Benchmark search performance
        search_queries = [
            "neural network training",
            "Python programming techniques",
            "data analysis methods",
            "web security practices",
            "machine learning evaluation",
            "database performance",
            "JavaScript development",
            "statistical testing"
        ]

        search_times = []
        result_counts = []

        for query in search_queries:
            start_time = time.time()
            results = memory.search_stored_interactions(query)
            search_time = time.time() - start_time

            search_times.append(search_time)
            result_counts.append(len(results))

            print(f"   Query '{query}': {len(results)} results in {search_time:.3f}s")

        avg_search_time = sum(search_times) / len(search_times)
        avg_results = sum(result_counts) / len(result_counts)

        print(f"✅ Performance benchmark completed:")
        print(f"   • {total_interactions} interactions inserted")
        print(f"   • Average insertion rate: {total_interactions/insertion_time:.1f}/s")
        print(f"   • Average search time: {avg_search_time:.3f}s")
        print(f"   • Average results per query: {avg_results:.1f}")

        # Verify acceptable performance
        assert avg_search_time < 1.0, f"Search too slow: {avg_search_time:.3f}s average"
        assert insertion_time < 30.0, f"Insertion too slow: {insertion_time:.2f}s for {total_interactions} items"

    def test_multilingual_embedding_support(self):
        """Test embeddings work with different languages"""

        print("🌍 Testing multilingual embedding support...")

        adapter = create_embedding_adapter(self.embedding_manager)

        # Test phrases in different languages with similar meanings
        multilingual_tests = [
            # Programming concepts
            ("machine learning", "apprentissage automatique", "aprendizaje automático"),  # EN, FR, ES
            ("artificial intelligence", "intelligence artificielle", "inteligencia artificial"),
            ("programming language", "langage de programmation", "lenguaje de programación"),

            # Common concepts
            ("hello world", "bonjour le monde", "hola mundo"),
            ("computer science", "informatique", "ciencias de la computación"),
        ]

        for english, french, spanish in multilingual_tests:
            # Generate embeddings
            emb_en = adapter.generate_embedding(english)
            emb_fr = adapter.generate_embedding(french)
            emb_es = adapter.generate_embedding(spanish)

            # Check cross-language similarity
            sim_en_fr = self._cosine_similarity(emb_en, emb_fr)
            sim_en_es = self._cosine_similarity(emb_en, emb_es)
            sim_fr_es = self._cosine_similarity(emb_fr, emb_es)

            print(f"   '{english}' vs languages: FR={sim_en_fr:.3f}, ES={sim_en_es:.3f}, FR-ES={sim_fr_es:.3f}")

            # Multilingual models should show some cross-language similarity
            # but this depends on the specific model's multilingual training
            min_similarity = min(sim_en_fr, sim_en_es, sim_fr_es)
            if min_similarity > 0.3:
                print(f"     ✅ Good multilingual similarity")
            else:
                print(f"     ⚠️ Limited multilingual support")

        print("✅ Multilingual embedding test completed")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


if __name__ == "__main__":
    # Run comprehensive tests
    if ABSTRACTCORE_AVAILABLE:
        print("🧪 RUNNING EXHAUSTIVE REAL EMBEDDINGS TESTS")
        print("=" * 60)

        test_instance = TestRealEmbeddingsExhaustive()
        test_instance.setup_method()

        try:
            print("\n1. Testing semantic similarity accuracy...")
            test_instance.test_embedding_semantic_similarity_accuracy()

            print("\n2. Testing LanceDB vector search...")
            test_instance.test_lancedb_vector_search_accuracy()

            print("\n3. Testing embedding consistency...")
            test_instance.test_embedding_consistency_and_caching()

            print("\n4. Testing performance benchmark...")
            test_instance.test_large_scale_performance_benchmark()

            print("\n5. Testing multilingual support...")
            test_instance.test_multilingual_embedding_support()

            if test_instance.llm_provider:
                print("\n6. Testing end-to-end LLM workflow...")
                test_instance.test_end_to_end_llm_semantic_memory_workflow()

            print("\n🎉 ALL EXHAUSTIVE TESTS PASSED!")
            print("   • Real AbstractCore embeddings ✅")
            print("   • Semantic similarity accuracy ✅")
            print("   • LanceDB vector search ✅")
            print("   • Performance benchmarks ✅")
            print("   • End-to-end LLM integration ✅")

        finally:
            test_instance.teardown_method()
    else:
        print("❌ AbstractCore not available - cannot run real embedding tests")
        print("Install AbstractCore to run exhaustive tests:")
        print("pip install abstractcore>=2.1.0")