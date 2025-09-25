
SHOULD IT BE IN ABSTRACT MEMORY OR ABSTRACT CORE ?
- handle file attachment
    - session : every file ever referenced
    - file currently attached to the context


whenever a new facts or knowledge is created (long term), emit an event through the MAIN ABSTRACT CORE event system
However, the definition of this event is probably made here ? and the trigger absolutely
=> could enable to display toaster message whenever a new knowledge is learnet
=> be carefull for fact eg 1500 facts in one discussion


pytest
================================================= test session starts ==================================================
platform darwin -- Python 3.12.2, pytest-8.4.1, pluggy-1.6.0
codspeed: 3.2.0 (disabled, mode: walltime, timer_resolution: 41.7ns)
benchmark: 5.1.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /Users/albou/projects
configfile: pyproject.toml
plugins: recording-0.13.4, docker-3.1.2, anyio-4.9.0, syrupy-4.9.1, socket-0.7.0, opik-1.8.1, Faker-37.4.0, dash-3.1.1, codspeed-3.2.0, langsmith-0.3.45, benchmark-5.1.0, asyncio-0.26.0, hydra-core-1.3.2, cov-6.1.1
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 217 items                                                                                                    

tests/components/test_core_memory.py ....................                                                        [  9%]
tests/components/test_episodic_memory.py ................                                                        [ 16%]
tests/components/test_semantic_memory.py ...............                                                         [ 23%]
tests/components/test_working_memory.py .............                                                            [ 29%]
tests/core/test_interfaces.py ...........                                                                        [ 34%]
tests/core/test_temporal.py .................                                                                    [ 42%]
tests/graph/test_knowledge_graph.py ..................                                                           [ 50%]
tests/integration/test_complete_llm_embedding_workflow.py ..                                                                                                                          [ 51%]
tests/integration/test_embeddings_diagnostic.py .                                                                                                                                     [ 52%]
tests/integration/test_grounded_memory.py ....................                                                                                                                        [ 61%]
tests/integration/test_llm_real_usage.py ......                                                                                                                                       [ 64%]
tests/integration/test_real_embeddings_exhaustive.py ......                                                                                                                           [ 66%]
tests/integration/test_real_embeddings_focused.py .                                                                                                                                   [ 67%]
tests/integration/test_real_llm_integration.py sssssss                                                                                                                                [ 70%]
tests/integration/test_two_tier_strategy.py .........                                                                                                                                 [ 74%]
tests/integration/test_verbatim_plus_embeddings_proof.py .                                                                                                                            [ 75%]
tests/simple/test_buffer_memory.py .........                                                                                                                                          [ 79%]
tests/simple/test_scratchpad_memory.py ............                                                                                                                                   [ 84%]
tests/storage/test_dual_manager.py .......                                                                                                                                            [ 88%]
tests/storage/test_dual_storage_comprehensive.py .........                                                                                                                            [ 92%]
tests/storage/test_grounded_memory_storage.py .........                                                                                                                               [ 96%]
tests/storage/test_markdown_storage.py ........                                                                                                                                       [100%]

===================================================================================== warnings summary ======================================================================================
abstractmemory/tests/integration/test_complete_llm_embedding_workflow.py::TestCompleteLLMEmbeddingWorkflow::test_complete_workflow_verbatim_plus_semantic_search
  /opt/anaconda3/lib/python3.12/site-packages/_pytest/python.py:161: PytestReturnNotNoneWarning: Test functions should return None, but abstractmemory/tests/integration/test_complete_llm_embedding_workflow.py::TestCompleteLLMEmbeddingWorkflow::test_complete_workflow_verbatim_plus_semantic_search returned <class 'bool'>.
  Did you mean to use `assert` instead of `return`?
  See https://docs.pytest.org/en/stable/how-to/assert.html#return-not-none for more information.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================================================================== 210 passed, 7 skipped, 1 warning in 572.83s (0:09:32) ===================================================================


=> why the skipped tests





# ❌ Before: BasicSession (no memory)
from abstractllm import BasicSession
session = BasicSession(provider)
response = session.generate("Hello, I'm Alice and I love Python")  # Forgets immediately

=> that's not true, BasicSession still has a chat history, so it would remember for as long as the chat history is in the active context