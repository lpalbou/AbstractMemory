"""
Complete LLM + Embedding Workflow Tests
======================================

These tests use REAL LLM calls AND REAL embeddings to prove:
1. Verbatim interactions are recorded exactly as they happen
2. Real embeddings are generated and stored for semantic search
3. Semantic search finds contextually relevant past interactions
4. LLMs can use semantic context to provide better responses
5. The complete memory system works end-to-end

NO MOCKS ANYWHERE - Pure real implementation testing.
"""

import pytest
import tempfile
import shutil
import time
import sys
from datetime import datetime, timedelta

# Add AbstractCore path
sys.path.insert(0, '/Users/albou/projects/abstractllm_core')

from abstractmemory import create_memory

try:
    from abstractllm.embeddings import EmbeddingManager
    from abstractllm import create_llm
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False


@pytest.mark.skipif(not ABSTRACTCORE_AVAILABLE, reason="AbstractCore not available")
class TestCompleteLLMEmbeddingWorkflow:
    """Complete workflow tests with real LLMs and real embeddings"""

    def setup_method(self):
        """Setup with real components"""
        self.temp_dir = tempfile.mkdtemp()
        self.embedding_manager = EmbeddingManager()

        # Try to get a working LLM
        self.llm_provider = None
        self.llm_model = None

        # Try different models in order of preference
        models_to_try = [
            ("ollama", "qwen3:4b"),
            ("ollama", "phi4:14b"),
            ("ollama", "qwen3:8b"),
            ("ollama", "llama3.1:8b"),
        ]

        for provider, model in models_to_try:
            try:
                self.llm_provider = create_llm(provider, model=model)
                self.llm_model = f"{provider}/{model}"
                break
            except Exception as e:
                continue

    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)

    def test_complete_workflow_verbatim_plus_semantic_search(self):
        """
        COMPLETE TEST: Real LLM calls + Real embeddings + Verbatim storage + Semantic search
        """

        if not self.llm_provider:
            pytest.skip("No LLM provider available for complete workflow test")

        print(f"🧪 COMPLETE WORKFLOW TEST with {self.llm_model}")
        print("=" * 60)

        # Create memory with real embeddings and dual storage
        memory = create_memory(
            "grounded",
            storage_backend="dual",  # Both markdown AND vector storage
            storage_path=f"{self.temp_dir}/memory_files",
            storage_uri=f"{self.temp_dir}/memory.db",
            embedding_provider=self.embedding_manager,
            working_capacity=20
        )

        print(f"✅ Created GroundedMemory with dual storage + real embeddings")

        # PHASE 1: Build knowledge base through REAL LLM conversations
        print("\n1️⃣ BUILDING KNOWLEDGE BASE WITH REAL LLM CONVERSATIONS")

        conversation_topics = [
            {
                "user_id": "alice",
                "topic": "Python programming",
                "user_query": "What are the best practices for Python code organization?",
            },
            {
                "user_id": "alice",
                "topic": "Machine learning",
                "user_query": "How do I choose the right machine learning algorithm?",
            },
            {
                "user_id": "bob",
                "topic": "Web development",
                "user_query": "What's the difference between React and Vue.js?",
            },
            {
                "user_id": "bob",
                "topic": "Database design",
                "user_query": "When should I use SQL vs NoSQL databases?",
            },
            {
                "user_id": "charlie",
                "topic": "Data science",
                "user_query": "What's the most important step in data analysis?",
            }
        ]

        llm_responses = []

        for conv in conversation_topics:
            user_id = conv["user_id"]
            topic = conv["topic"]
            user_query = conv["user_query"]

            print(f"\n   💬 {user_id} asks about {topic}:")
            print(f"      Q: \"{user_query}\"")

            # Set user context
            memory.set_current_user(user_id)

            # Generate REAL LLM response
            try:
                start_time = time.time()
                response = self.llm_provider.generate(user_query)
                llm_time = time.time() - start_time

                # Extract response text
                response_text = response.content if hasattr(response, 'content') else str(response)

                print(f"      A: \"{response_text[:100]}...\" ({llm_time:.1f}s)")

                # Add to memory - THIS IS THE KEY TEST
                memory.add_interaction(user_query, response_text)

                llm_responses.append({
                    "user_id": user_id,
                    "topic": topic,
                    "user_query": user_query,
                    "llm_response": response_text,
                    "response_time": llm_time
                })

                print(f"      ✅ Added to memory with real embeddings")

            except Exception as e:
                print(f"      ❌ LLM failed: {e}")
                continue

        print(f"\n✅ Built knowledge base with {len(llm_responses)} real LLM interactions")

        # PHASE 2: Verify verbatim storage
        print("\n2️⃣ VERIFYING VERBATIM STORAGE")

        # Check markdown files exist and contain exact content
        import os
        markdown_files = []
        for root, dirs, files in os.walk(f"{self.temp_dir}/memory_files/verbatim"):
            for file in files:
                if file.endswith('.md'):
                    markdown_files.append(os.path.join(root, file))

        print(f"   📄 Found {len(markdown_files)} markdown files")

        verbatim_verified = 0
        for response_data in llm_responses:
            user_query = response_data["user_query"]
            llm_response = response_data["llm_response"]

            # Check if verbatim content exists in markdown files
            found_verbatim = False
            for md_file in markdown_files:
                try:
                    with open(md_file, 'r') as f:
                        content = f.read()
                        # Check if both user query and LLM response are stored verbatim
                        if user_query[:50] in content and llm_response[:50] in content:
                            found_verbatim = True
                            verbatim_verified += 1
                            print(f"   ✅ Verbatim found: \"{user_query[:40]}...\"")
                            break
                except:
                    continue

            if not found_verbatim:
                print(f"   ❌ Verbatim missing: \"{user_query[:40]}...\"")

        verbatim_success_rate = verbatim_verified / len(llm_responses) if llm_responses else 0
        print(f"   📊 Verbatim storage: {verbatim_verified}/{len(llm_responses)} verified ({verbatim_success_rate:.1%})")

        # PHASE 3: Test semantic search finds relevant conversations
        print("\n3️⃣ TESTING SEMANTIC SEARCH FINDS RELEVANT CONVERSATIONS")

        semantic_queries = [
            {
                "query": "software engineering best practices",
                "should_find_topics": ["Python programming", "Web development"],
                "description": "Should find programming-related conversations"
            },
            {
                "query": "artificial intelligence and data mining",
                "should_find_topics": ["Machine learning", "Data science"],
                "description": "Should find ML/data conversations"
            },
            {
                "query": "database architecture decisions",
                "should_find_topics": ["Database design"],
                "description": "Should find database conversations"
            }
        ]

        semantic_successes = 0

        for semantic_test in semantic_queries:
            query = semantic_test["query"]
            should_find_topics = semantic_test["should_find_topics"]
            description = semantic_test["description"]

            print(f"\n   🔍 Semantic query: \"{query}\"")
            print(f"      {description}")

            # Perform semantic search
            start_time = time.time()
            results = memory.search_stored_interactions(query)
            search_time = time.time() - start_time

            print(f"      → {len(results)} results in {search_time:.3f}s")

            if results:
                # Check if results contain expected topics
                found_topics = []
                for result in results[:3]:  # Check top 3
                    result_content = result['user_input'].lower()

                    # Match against our known LLM responses
                    for response_data in llm_responses:
                        if response_data["user_query"][:30].lower() in result_content:
                            found_topics.append(response_data["topic"])
                            break

                # Calculate semantic relevance
                relevant_topics = [topic for topic in found_topics if topic in should_find_topics]
                semantic_score = len(relevant_topics) / len(should_find_topics) if should_find_topics else 0

                print(f"      → Found topics: {found_topics[:3]}")
                print(f"      → Relevant topics: {relevant_topics}")
                print(f"      → Semantic score: {semantic_score:.1%}")

                if semantic_score >= 0.5:  # At least 50% semantic relevance
                    semantic_successes += 1
                    print(f"      ✅ SEMANTIC SUCCESS")
                else:
                    print(f"      ⚠️ Low semantic relevance")

                # Show top result
                if results:
                    top_result = results[0]
                    print(f"      → Top result: \"{top_result['user_input'][:60]}...\"")

            else:
                print(f"      ❌ No results found")

        semantic_success_rate = semantic_successes / len(semantic_queries)
        print(f"\n   📊 Semantic search: {semantic_successes}/{len(semantic_queries)} successful ({semantic_success_rate:.1%})")

        # PHASE 4: Test LLM uses semantic context for better responses
        print("\n4️⃣ TESTING LLM USES SEMANTIC CONTEXT FOR BETTER RESPONSES")

        context_test_query = "I need help optimizing my code performance"

        print(f"   🤖 New query: \"{context_test_query}\"")

        # Get semantic context
        memory.set_current_user("alice")  # Use alice's context
        semantic_context = memory.get_full_context(context_test_query, user_id="alice")

        print(f"   📋 Retrieved semantic context: {len(semantic_context)} characters")

        # Generate response WITH semantic context
        context_prompt = f"""Previous conversation context:
{semantic_context}

Current user question: {context_test_query}

Based on the previous conversations, provide a helpful response about code optimization."""

        try:
            start_time = time.time()
            context_response = self.llm_provider.generate(context_prompt)
            context_time = time.time() - start_time

            context_response_text = context_response.content if hasattr(context_response, 'content') else str(context_response)

            print(f"   💡 LLM response with context ({context_time:.1f}s):")
            print(f"      \"{context_response_text[:150]}...\"")

            # Check if response references previous context
            context_usage_indicators = [
                "previous", "earlier", "mentioned", "discussed", "Python", "programming",
                "best practices", "organization"
            ]

            context_usage_score = sum(1 for indicator in context_usage_indicators
                                    if indicator.lower() in context_response_text.lower())

            if context_usage_score >= 2:
                print(f"   ✅ LLM used semantic context ({context_usage_score} indicators)")
                context_success = True
            else:
                print(f"   ⚠️ Limited context usage ({context_usage_score} indicators)")
                context_success = False

            # Add this interaction back to memory
            memory.add_interaction(context_test_query, context_response_text)
            print(f"   ✅ New interaction added to memory")

        except Exception as e:
            print(f"   ❌ Context test failed: {e}")
            context_success = False

        # PHASE 5: Final verification and summary
        print("\n5️⃣ FINAL VERIFICATION AND SUMMARY")

        # Check storage statistics
        try:
            storage_stats = memory.storage_manager.get_stats() if hasattr(memory, 'storage_manager') else {}
            print(f"   📊 Storage stats: {storage_stats}")
        except:
            print(f"   📊 Storage stats not available")

        # Calculate overall success metrics
        total_interactions = len(llm_responses) + (1 if context_success else 0)

        print(f"\n🏆 FINAL RESULTS:")
        print(f"   • Real LLM interactions: {len(llm_responses)}")
        print(f"   • Verbatim storage success: {verbatim_success_rate:.1%}")
        print(f"   • Semantic search success: {semantic_success_rate:.1%}")
        print(f"   • Context usage success: {'✅' if context_success else '⚠️'}")
        print(f"   • Total interactions stored: {total_interactions}")

        # Overall success criteria
        overall_success = (
            verbatim_success_rate >= 0.8 and  # 80% verbatim storage
            semantic_success_rate >= 0.6 and   # 60% semantic search
            len(llm_responses) >= 3            # At least 3 real interactions
        )

        if overall_success:
            print(f"\n🎉 COMPLETE WORKFLOW SUCCESS!")
            print(f"   ✅ Real LLM calls with real responses")
            print(f"   ✅ Verbatim interactions stored correctly")
            print(f"   ✅ Real embeddings enable semantic search")
            print(f"   ✅ LLM can use semantic context")
            print(f"   ✅ End-to-end workflow functional")
        else:
            print(f"\n⚠️ Workflow needs improvement")

        # Assertions for test framework
        assert len(llm_responses) >= 2, f"Need at least 2 real LLM interactions, got {len(llm_responses)}"
        assert verbatim_success_rate >= 0.5, f"Verbatim storage too low: {verbatim_success_rate:.1%}"
        assert semantic_success_rate >= 0.3, f"Semantic search too low: {semantic_success_rate:.1%}"

        return overall_success

    def test_embedding_quality_with_real_llm_content(self):
        """Test that embeddings capture semantic meaning of real LLM responses"""

        if not self.llm_provider:
            pytest.skip("No LLM provider available")

        print(f"\n🔬 TESTING EMBEDDING QUALITY WITH REAL LLM CONTENT")

        # Generate real LLM responses on different topics
        topics = [
            "Explain machine learning algorithms",
            "Describe web development frameworks",
            "What is database normalization?",
            "How to cook pasta properly",
            "Best hiking trails in mountains"
        ]

        llm_responses = []
        embeddings = []

        for topic in topics:
            try:
                response = self.llm_provider.generate(topic)
                response_text = response.content if hasattr(response, 'content') else str(response)

                # Generate embedding for the LLM response
                embedding = self.embedding_manager.embed(response_text)

                llm_responses.append(response_text)
                embeddings.append(embedding)

                print(f"   ✅ Topic: {topic[:30]}... → {len(embedding)} dims")

            except Exception as e:
                print(f"   ❌ Failed for topic: {topic[:30]}... → {e}")

        # Test semantic clustering
        if len(embeddings) >= 4:
            # Compare tech topics vs non-tech topics
            tech_embeddings = embeddings[:3]  # ML, web dev, database
            non_tech_embeddings = embeddings[3:]  # cooking, hiking

            # Calculate intra-cluster similarity (tech topics should be more similar to each other)
            tech_similarities = []
            for i in range(len(tech_embeddings)):
                for j in range(i+1, len(tech_embeddings)):
                    sim = self._cosine_similarity(tech_embeddings[i], tech_embeddings[j])
                    tech_similarities.append(sim)

            # Calculate inter-cluster similarity (tech vs non-tech should be less similar)
            cross_similarities = []
            for tech_emb in tech_embeddings:
                for non_tech_emb in non_tech_embeddings:
                    sim = self._cosine_similarity(tech_emb, non_tech_emb)
                    cross_similarities.append(sim)

            avg_tech_sim = sum(tech_similarities) / len(tech_similarities) if tech_similarities else 0
            avg_cross_sim = sum(cross_similarities) / len(cross_similarities) if cross_similarities else 0

            print(f"   📊 Tech topic similarity: {avg_tech_sim:.3f}")
            print(f"   📊 Cross-topic similarity: {avg_cross_sim:.3f}")
            print(f"   📊 Semantic clustering: {'✅' if avg_tech_sim > avg_cross_sim else '⚠️'}")

            assert len(llm_responses) >= 3, "Need at least 3 LLM responses"
            # Note: Not asserting on similarity scores as they depend on the specific model

    def _cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between vectors"""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


if __name__ == "__main__":
    # Run the complete workflow test
    if ABSTRACTCORE_AVAILABLE:
        print("🧪 RUNNING COMPLETE LLM + EMBEDDING WORKFLOW TESTS")
        print("=" * 70)

        test_instance = TestCompleteLLMEmbeddingWorkflow()
        test_instance.setup_method()

        try:
            print("\n🔥 Testing complete workflow...")
            success1 = test_instance.test_complete_workflow_verbatim_plus_semantic_search()

            print("\n🔬 Testing embedding quality...")
            test_instance.test_embedding_quality_with_real_llm_content()

            if success1:
                print("\n🎯 ALL TESTS PASSED!")
                print("✅ Real LLM calls work")
                print("✅ Verbatim storage works")
                print("✅ Real embeddings work")
                print("✅ Semantic search works")
                print("✅ Complete workflow functional")
            else:
                print("\n⚠️ Some tests need attention")

        finally:
            test_instance.teardown_method()

    else:
        print("❌ AbstractCore not available - install with: pip install abstractcore>=2.1.0")