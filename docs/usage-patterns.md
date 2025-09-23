# Usage Patterns Guide

This guide demonstrates real-world usage patterns for AbstractMemory across different agent types and scenarios, with practical code examples and best practices.

## 📋 Table of Contents

1. [ReAct Agents with ScratchpadMemory](#react-agents)
2. [Chatbots with BufferMemory](#chatbots)
3. [Personal Assistants with GroundedMemory](#personal-assistants)
4. [Multi-User Systems](#multi-user-systems)
5. [Learning from Experience](#learning-patterns)
6. [Advanced Integration Patterns](#advanced-patterns)

## 🤖 ReAct Agents with ScratchpadMemory {#react-agents}

### Code Generation Agent

```python
from abstractmemory import create_memory

class CodeGenerationAgent:
    def __init__(self):
        self.memory = create_memory("scratchpad", max_entries=100)
        self.llm = None  # Your LLM provider

    def generate_code(self, request: str) -> str:
        # Think about the request
        self.memory.add_thought(f"User wants: {request}")
        self.memory.add_thought("Need to break this down into steps")

        # Plan the implementation
        self.memory.add_action("analyze_requirements", {"request": request})
        self.memory.add_observation("Requirements: function with error handling")

        # Generate code structure
        self.memory.add_thought("Starting with function signature")
        self.memory.add_action("generate_structure", {"type": "function"})
        self.memory.add_observation("Created basic function template")

        # Implement logic
        self.memory.add_thought("Adding core logic and error handling")
        self.memory.add_action("implement_logic", {"pattern": "try-except"})
        self.memory.add_observation("Logic implemented with proper error handling")

        # Get context for final generation
        context = self.memory.get_context()

        # Use LLM with memory context
        response = self.llm.generate(
            prompt=request,
            system_prompt=f"Code generation context:\n{context}\n\nGenerate clean, well-documented code."
        )

        return response.content

# Usage example
agent = CodeGenerationAgent()
code = agent.generate_code("Create a function to validate email addresses")
```

### Web Research Agent

```python
class WebResearchAgent:
    def __init__(self):
        self.memory = create_memory("scratchpad", max_entries=50)
        self.web_tool = None  # Your web search tool

    def research_topic(self, topic: str) -> str:
        self.memory.add_thought(f"Research topic: {topic}")
        self.memory.add_thought("Need to find reliable sources")

        # Search for information
        self.memory.add_action("web_search", {"query": topic, "num_results": 5})
        search_results = self.web_tool.search(topic)
        self.memory.add_observation(f"Found {len(search_results)} relevant sources")

        # Analyze credibility
        self.memory.add_thought("Evaluating source credibility")
        self.memory.add_action("analyze_sources", {"criteria": "authority, recency, relevance"})
        credible_sources = [s for s in search_results if s.is_credible()]
        self.memory.add_observation(f"Identified {len(credible_sources)} credible sources")

        # Extract key information
        self.memory.add_thought("Extracting key information from credible sources")
        for i, source in enumerate(credible_sources[:3]):
            self.memory.add_action("extract_info", {"source": source.url})
            info = source.extract_key_points()
            self.memory.add_observation(f"Source {i+1}: {info[:100]}...")

        # Synthesize findings
        self.memory.add_thought("Synthesizing information from multiple sources")
        context = self.memory.get_context()

        # Generate comprehensive summary
        summary = self.llm.generate(
            prompt=f"Synthesize research on: {topic}",
            system_prompt=f"Research context:\n{context}\n\nProvide factual, well-sourced summary."
        )

        return summary.content
```

### Mathematical Problem Solver

```python
class MathSolverAgent:
    def __init__(self):
        self.memory = create_memory("scratchpad", max_entries=75)

    def solve_problem(self, problem: str) -> str:
        self.memory.add_thought(f"Math problem: {problem}")
        self.memory.add_thought("Breaking down the problem step by step")

        # Identify problem type
        self.memory.add_action("classify_problem", {"text": problem})
        problem_type = self.classify_problem(problem)
        self.memory.add_observation(f"Problem type: {problem_type}")

        # Plan solution approach
        self.memory.add_thought(f"For {problem_type}, I'll use standard approach")
        self.memory.add_action("plan_solution", {"type": problem_type})
        approach = self.get_solution_approach(problem_type)
        self.memory.add_observation(f"Solution approach: {approach}")

        # Solve step by step
        steps = self.break_down_solution(problem)
        for i, step in enumerate(steps):
            self.memory.add_thought(f"Step {i+1}: {step.description}")
            self.memory.add_action("calculate", step.operation)
            result = self.execute_step(step)
            self.memory.add_observation(f"Result: {result}")

        # Verify solution
        self.memory.add_thought("Verifying the solution")
        self.memory.add_action("verify", {"method": "substitution"})
        is_correct = self.verify_solution(problem, result)
        self.memory.add_observation(f"Verification: {'Correct' if is_correct else 'Error detected'}")

        # Format final answer
        context = self.memory.get_context()
        return self.format_solution(context, result)
```

## 💬 Chatbots with BufferMemory {#chatbots}

### Customer Service Bot

```python
class CustomerServiceBot:
    def __init__(self):
        self.memory = create_memory("buffer", max_messages=200)
        self.knowledge_base = None  # Your KB system

    def handle_conversation(self, user_message: str) -> str:
        # Add user message to memory
        self.memory.add_message("user", user_message)

        # Get conversation context
        context = self.memory.get_context()
        recent_messages = self.memory.get_recent_messages(10)

        # Determine intent from conversation history
        intent = self.analyze_intent(user_message, recent_messages)

        # Generate contextual response
        if intent == "product_inquiry":
            response = self.handle_product_inquiry(user_message, context)
        elif intent == "technical_support":
            response = self.handle_technical_support(user_message, context)
        elif intent == "billing":
            response = self.handle_billing_inquiry(user_message, context)
        else:
            response = self.generate_general_response(user_message, context)

        # Add assistant response to memory
        self.memory.add_message("assistant", response)

        return response

    def handle_product_inquiry(self, message: str, context: str) -> str:
        # Use conversation context to provide relevant information
        relevant_products = self.knowledge_base.search(message, context=context)

        response = self.llm.generate(
            prompt=message,
            system_prompt=f"""You are a helpful customer service agent.
            Conversation history: {context}

            Available products: {relevant_products}

            Provide helpful, contextual product information."""
        )

        return response.content

# Usage example
bot = CustomerServiceBot()

# Conversation flow
response1 = bot.handle_conversation("I'm looking for a laptop")
response2 = bot.handle_conversation("Something good for programming")
response3 = bot.handle_conversation("What about the price range?")
# Bot maintains context throughout the conversation
```

### FAQ Bot with Context

```python
class ContextualFAQBot:
    def __init__(self):
        self.memory = create_memory("buffer", max_messages=100)
        self.faq_database = None

    def answer_question(self, question: str) -> str:
        self.memory.add_message("user", question)

        # Use conversation history for better context
        conversation_context = self.memory.get_context()
        previous_topics = self.extract_topics_from_history()

        # Find relevant FAQ entries
        faq_matches = self.faq_database.search(
            query=question,
            context_topics=previous_topics,
            conversation_history=conversation_context
        )

        # Generate contextual answer
        if faq_matches:
            answer = self.generate_contextual_answer(question, faq_matches, conversation_context)
        else:
            answer = self.generate_fallback_response(question, conversation_context)

        self.memory.add_message("assistant", answer)
        return answer

    def extract_topics_from_history(self) -> list:
        messages = self.memory.get_recent_messages(5)
        topics = []
        for msg in messages:
            if msg["role"] == "user":
                extracted_topics = self.topic_extractor.extract(msg["content"])
                topics.extend(extracted_topics)
        return list(set(topics))  # Remove duplicates
```

## 🧠 Personal Assistants with GroundedMemory {#personal-assistants}

### Personal Programming Assistant

```python
class PersonalProgrammingAssistant:
    def __init__(self):
        self.memory = create_memory(
            "grounded",
            working_capacity=15,
            enable_kg=True,
            semantic_threshold=3
        )

    def initialize_user(self, user_id: str, preferences: dict):
        """Initialize user profile"""
        self.memory.set_current_user(user_id, relationship="owner")

        # Learn about user's programming background
        for skill, level in preferences.get("skills", {}).items():
            self.memory.learn_about_user(f"Programming skill: {skill} (level: {level})")

        # Learn preferences
        for pref in preferences.get("preferences", []):
            self.memory.learn_about_user(f"Preference: {pref}")

    def provide_programming_help(self, user_id: str, request: str) -> str:
        # Switch to user context
        self.memory.set_current_user(user_id)

        # Add interaction to memory
        response = self.generate_response(request)
        self.memory.add_interaction(request, response)

        # Learn from the interaction
        self.extract_and_learn_facts(request, response)

        return response

    def generate_response(self, request: str) -> str:
        # Get full personalized context
        context = self.memory.get_full_context(request)

        # Generate response using user-specific context
        response = self.llm.generate(
            prompt=request,
            system_prompt=f"""You are a personal programming assistant.

            {context}

            Provide personalized help based on the user's background and preferences.
            Remember their skill level and tailor explanations accordingly."""
        )

        return response.content

    def extract_and_learn_facts(self, request: str, response: str):
        """Extract facts from conversation for learning"""
        # Extract user preferences
        if "prefer" in request.lower():
            self.memory.learn_about_user(f"Expressed preference: {request}")

        # Extract technology mentions
        technologies = self.extract_technologies(request + " " + response)
        for tech in technologies:
            self.memory.learn_about_user(f"Uses technology: {tech}")

        # Track successful patterns
        if self.is_positive_feedback(request):
            context = self.extract_context_from_request(request)
            self.memory.track_success("programming_help", context)

# Usage example
assistant = PersonalProgrammingAssistant()

# Initialize user
assistant.initialize_user("alice", {
    "skills": {"python": "intermediate", "javascript": "beginner"},
    "preferences": ["detailed explanations", "practical examples", "best practices"]
})

# Conversation over time
response1 = assistant.provide_programming_help("alice", "How do I handle errors in Python?")
response2 = assistant.provide_programming_help("alice", "What about async programming?")
response3 = assistant.provide_programming_help("alice", "Can you explain decorators?")

# Assistant learns user's level and adjusts explanations
```

### Life Management Assistant

```python
class LifeManagementAssistant:
    def __init__(self):
        self.memory = create_memory(
            "grounded",
            working_capacity=20,
            enable_kg=True,
            semantic_threshold=2
        )

    def help_with_task(self, user_id: str, task_description: str) -> str:
        self.memory.set_current_user(user_id)

        # Analyze task based on user's history
        user_context = self.memory.get_full_context(task_description, user_id)
        task_analysis = self.analyze_task(task_description, user_context)

        # Generate personalized advice
        advice = self.generate_personalized_advice(task_description, task_analysis, user_context)

        # Record interaction
        self.memory.add_interaction(task_description, advice)

        # Learn from the interaction
        self.learn_from_task(task_description, user_id)

        return advice

    def learn_from_task(self, task: str, user_id: str):
        """Learn patterns from user's tasks"""
        # Extract categories
        category = self.categorize_task(task)
        self.memory.learn_about_user(f"Frequently works on: {category}")

        # Extract timing patterns
        current_time = datetime.now()
        time_of_day = self.get_time_category(current_time)
        self.memory.learn_about_user(f"Active during: {time_of_day}")

        # Track productivity patterns
        if self.is_productivity_task(task):
            self.memory.track_success("productivity_planning", category)

    def provide_proactive_suggestions(self, user_id: str) -> list:
        """Provide proactive suggestions based on learned patterns"""
        self.memory.set_current_user(user_id)

        # Get user's patterns
        user_facts = self.memory.semantic.retrieve("frequently works")
        time_patterns = self.memory.semantic.retrieve("active during")

        # Generate suggestions based on current time and patterns
        current_context = self.get_current_context()
        suggestions = self.generate_suggestions(user_facts, time_patterns, current_context)

        return suggestions

# Usage example
assistant = LifeManagementAssistant()

# User interactions over time
assistant.help_with_task("bob", "I need to organize my home office")
assistant.help_with_task("bob", "Plan my workout routine")
assistant.help_with_task("bob", "Schedule my work meetings")

# Assistant learns Bob's patterns and provides proactive suggestions
suggestions = assistant.provide_proactive_suggestions("bob")
```

## 👥 Multi-User Systems {#multi-user-systems}

### Multi-Tenant Support System

```python
class MultiTenantSupportSystem:
    def __init__(self):
        self.memory = create_memory(
            "grounded",
            working_capacity=10,
            enable_kg=True,
            semantic_threshold=3
        )
        self.active_sessions = {}

    def start_session(self, user_id: str, relationship: str = "customer"):
        """Start a new user session"""
        self.memory.set_current_user(user_id, relationship=relationship)
        self.active_sessions[user_id] = {
            "start_time": datetime.now(),
            "interaction_count": 0
        }

    def handle_user_request(self, user_id: str, request: str) -> str:
        # Switch to user's context
        self.memory.set_current_user(user_id)

        # Get user-specific context
        user_context = self.memory.get_full_context(request, user_id)

        # Check for escalation patterns
        if self.should_escalate(request, user_context):
            response = self.escalate_to_human(user_id, request)
        else:
            response = self.generate_support_response(request, user_context)

        # Record interaction
        self.memory.add_interaction(request, response)

        # Update session tracking
        self.active_sessions[user_id]["interaction_count"] += 1

        # Learn from interaction
        self.learn_from_support_interaction(user_id, request, response)

        return response

    def should_escalate(self, request: str, user_context: str) -> bool:
        """Determine if request should be escalated to human agent"""
        # Check for escalation indicators
        escalation_signals = [
            "speak to manager", "human agent", "not helpful",
            "frustrated", "cancel subscription", "legal action"
        ]

        if any(signal in request.lower() for signal in escalation_signals):
            return True

        # Check user's frustration history
        recent_interactions = self.memory.working.get_recent_items(5)
        negative_interactions = sum(1 for item in recent_interactions
                                  if self.sentiment_analyzer.is_negative(item.content))

        return negative_interactions >= 3

    def get_user_insights(self, user_id: str) -> dict:
        """Get insights about a specific user"""
        self.memory.set_current_user(user_id)

        # Get user's interaction history
        user_profile = self.memory.get_user_profile(user_id)

        # Get validated facts about user
        user_facts = self.memory.semantic.retrieve(f"user:{user_id}")

        # Get common issues
        user_episodes = self.memory.episodic.retrieve_by_user(user_id)

        return {
            "profile": user_profile,
            "validated_facts": [fact.content for fact in user_facts],
            "interaction_history": user_episodes,
            "common_issues": self.extract_common_issues(user_episodes)
        }

# Usage example
support_system = MultiTenantSupportSystem()

# Handle multiple users
support_system.start_session("customer_001", "premium_customer")
support_system.start_session("customer_002", "free_tier")

# Each user gets personalized context
response1 = support_system.handle_user_request("customer_001", "I'm having trouble with the advanced features")
response2 = support_system.handle_user_request("customer_002", "How do I upgrade my account?")

# System learns about each user separately
insights_001 = support_system.get_user_insights("customer_001")
insights_002 = support_system.get_user_insights("customer_002")
```

## 📈 Learning from Experience {#learning-patterns}

### Adaptive Code Review Assistant

```python
class AdaptiveCodeReviewAssistant:
    def __init__(self):
        self.memory = create_memory(
            "grounded",
            working_capacity=15,
            enable_kg=True,
            semantic_threshold=2
        )

    def review_code(self, user_id: str, code: str, language: str) -> dict:
        self.memory.set_current_user(user_id)

        # Get user's coding patterns and preferences
        user_context = self.memory.get_full_context(f"code review {language}")

        # Perform review
        review_result = self.perform_code_review(code, language, user_context)

        # Record interaction
        self.memory.add_interaction(
            f"Code review request for {language}",
            f"Provided {len(review_result['issues'])} suggestions"
        )

        # Learn from the review
        self.learn_from_code_review(user_id, language, code, review_result)

        return review_result

    def learn_from_code_review(self, user_id: str, language: str, code: str, review: dict):
        """Learn patterns from code reviews"""
        # Learn about user's coding style
        style_patterns = self.extract_style_patterns(code)
        for pattern in style_patterns:
            self.memory.learn_about_user(f"Coding style: {pattern}")

        # Learn about common issues
        for issue in review["issues"]:
            issue_type = issue["category"]
            self.memory.track_failure("code_quality", f"{language}:{issue_type}")

        # Learn about user preferences
        if review["user_feedback"]:
            if review["user_feedback"]["helpful"]:
                for suggestion in review["accepted_suggestions"]:
                    self.memory.track_success("code_suggestion", f"{language}:{suggestion['type']}")
            else:
                for suggestion in review["rejected_suggestions"]:
                    self.memory.track_failure("code_suggestion", f"{language}:{suggestion['type']}")

    def get_personalized_review_focus(self, user_id: str, language: str) -> list:
        """Get areas to focus on based on user's history"""
        self.memory.set_current_user(user_id)

        # Get user's common issues
        common_failures = self.memory.semantic.retrieve("code_quality failure")

        # Get successful suggestion patterns
        successful_patterns = self.memory.semantic.retrieve("code_suggestion success")

        # Generate focus areas
        focus_areas = []
        for failure in common_failures:
            if language in failure.content:
                focus_areas.append(failure.content.split(":")[-1])

        return focus_areas

# Usage example
assistant = AdaptiveCodeReviewAssistant()

# Initial reviews
review1 = assistant.review_code("dev_alice", python_code_1, "python")
review2 = assistant.review_code("dev_alice", python_code_2, "python")

# Assistant learns Alice's patterns
focus_areas = assistant.get_personalized_review_focus("dev_alice", "python")
# Now focuses on Alice's common issues and preferred suggestion types
```

### Learning Research Assistant

```python
class LearningResearchAssistant:
    def __init__(self):
        self.memory = create_memory(
            "grounded",
            working_capacity=20,
            enable_kg=True,
            semantic_threshold=2
        )

    def research_query(self, user_id: str, query: str, domain: str) -> dict:
        self.memory.set_current_user(user_id)

        # Get user's research patterns and expertise
        user_context = self.memory.get_full_context(f"research {domain}")

        # Perform research
        research_result = self.conduct_research(query, domain, user_context)

        # Adapt presentation based on user's expertise level
        expertise_level = self.assess_user_expertise(user_id, domain)
        formatted_result = self.format_for_expertise_level(research_result, expertise_level)

        # Record interaction
        self.memory.add_interaction(query, f"Research on {domain}: {query}")

        # Learn from research session
        self.learn_from_research(user_id, query, domain, research_result, formatted_result)

        return formatted_result

    def learn_from_research(self, user_id: str, query: str, domain: str, result: dict, formatted_result: dict):
        """Learn from research interactions"""
        # Learn about user's research interests
        topics = self.extract_topics(query)
        for topic in topics:
            self.memory.learn_about_user(f"Research interest: {topic}")

        # Learn about preferred depth and complexity
        if formatted_result["user_feedback"]:
            feedback = formatted_result["user_feedback"]
            if feedback["too_simple"]:
                self.memory.learn_about_user(f"Expertise level {domain}: advanced")
            elif feedback["too_complex"]:
                self.memory.learn_about_user(f"Expertise level {domain}: beginner")
            else:
                self.memory.learn_about_user(f"Expertise level {domain}: intermediate")

        # Track successful research strategies
        if feedback.get("helpful", False):
            strategy = result.get("strategy_used")
            self.memory.track_success("research_strategy", f"{domain}:{strategy}")

    def assess_user_expertise(self, user_id: str, domain: str) -> str:
        """Assess user's expertise level in domain"""
        self.memory.set_current_user(user_id)

        # Get user's expertise facts
        expertise_facts = self.memory.semantic.retrieve(f"expertise level {domain}")

        if expertise_facts:
            # Use most recent/confident expertise assessment
            latest_fact = max(expertise_facts, key=lambda x: x.confidence)
            return latest_fact.content.split(":")[-1].strip()

        # Default to intermediate if unknown
        return "intermediate"

# Usage example
assistant = LearningResearchAssistant()

# Research sessions adapt to user's growing expertise
result1 = assistant.research_query("researcher_bob", "machine learning algorithms", "ai")
result2 = assistant.research_query("researcher_bob", "neural network architectures", "ai")
result3 = assistant.research_query("researcher_bob", "transformer attention mechanisms", "ai")

# Assistant learns Bob's expertise level and adapts complexity
```

## 🔧 Advanced Integration Patterns {#advanced-patterns}

### Hybrid Memory Architecture

```python
class HybridAgent:
    """Agent that uses different memory types for different tasks"""

    def __init__(self):
        # Task-specific memory for structured reasoning
        self.task_memory = create_memory("scratchpad", max_entries=50)

        # Conversational memory for user interactions
        self.conversation_memory = create_memory("buffer", max_messages=100)

        # Long-term learning memory
        self.learning_memory = create_memory("grounded", working_capacity=10)

    def handle_task_request(self, user_id: str, task: str) -> str:
        # Use task memory for structured reasoning
        self.task_memory.add_thought(f"Task request: {task}")
        self.task_memory.add_thought("Breaking down into steps...")

        # Execute task with structured reasoning
        result = self.execute_task_with_reasoning(task)

        # Add to conversation memory for context
        self.conversation_memory.add_message("user", task)
        self.conversation_memory.add_message("assistant", result)

        # Learn patterns in long-term memory
        self.learning_memory.set_current_user(user_id)
        self.learning_memory.add_interaction(task, result)
        self.extract_task_patterns(task, result)

        return result

    def get_unified_context(self, query: str, user_id: str) -> str:
        """Combine insights from all memory types"""
        # Get task reasoning context
        task_context = self.task_memory.get_context()

        # Get conversation context
        conv_context = self.conversation_memory.get_context()

        # Get learned patterns
        self.learning_memory.set_current_user(user_id)
        learning_context = self.learning_memory.get_full_context(query)

        # Combine contexts intelligently
        unified_context = self.combine_contexts(task_context, conv_context, learning_context)

        return unified_context
```

### Memory Migration and Upgrade

```python
class MemoryMigrationManager:
    """Handles migration between memory types as agents evolve"""

    def migrate_simple_to_grounded(self, simple_memory, user_id: str):
        """Migrate from simple memory to grounded memory"""
        # Create new grounded memory
        grounded_memory = create_memory("grounded", working_capacity=15)
        grounded_memory.set_current_user(user_id)

        if isinstance(simple_memory, BufferMemory):
            # Migrate conversation history
            messages = simple_memory.get_all_messages()
            for i in range(0, len(messages), 2):
                if i + 1 < len(messages):
                    user_msg = messages[i]["content"]
                    assistant_msg = messages[i + 1]["content"]
                    grounded_memory.add_interaction(user_msg, assistant_msg)

        elif isinstance(simple_memory, ScratchpadMemory):
            # Convert reasoning traces to episodic memory
            context = simple_memory.get_context()
            grounded_memory.episodic.add(MemoryItem(
                content=f"Historical reasoning trace: {context}",
                event_time=datetime.now(),
                ingestion_time=datetime.now(),
                metadata={"type": "reasoning_history"}
            ))

        return grounded_memory

    def backup_memory_state(self, memory) -> dict:
        """Create backup of memory state"""
        if hasattr(memory, 'export_state'):
            return memory.export_state()
        else:
            # Fallback serialization
            return {
                "type": type(memory).__name__,
                "data": memory.get_serializable_state(),
                "timestamp": datetime.now().isoformat()
            }

    def restore_memory_state(self, backup_data: dict):
        """Restore memory from backup"""
        memory_type = backup_data["type"]

        if memory_type == "ScratchpadMemory":
            memory = create_memory("scratchpad")
        elif memory_type == "BufferMemory":
            memory = create_memory("buffer")
        elif memory_type == "GroundedMemory":
            memory = create_memory("grounded")

        if hasattr(memory, 'import_state'):
            memory.import_state(backup_data["data"])

        return memory
```

### Performance Monitoring and Optimization

```python
class MemoryPerformanceMonitor:
    """Monitor and optimize memory performance"""

    def __init__(self):
        self.metrics = {
            "operation_times": defaultdict(list),
            "memory_usage": defaultdict(list),
            "cache_hits": defaultdict(int),
            "cache_misses": defaultdict(int)
        }

    @contextmanager
    def measure_operation(self, operation_name: str, memory_type: str):
        """Context manager to measure operation performance"""
        start_time = time.time()
        start_memory = self.get_memory_usage()

        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self.get_memory_usage()

            operation_time = end_time - start_time
            memory_delta = end_memory - start_memory

            self.metrics["operation_times"][f"{memory_type}:{operation_name}"].append(operation_time)
            self.metrics["memory_usage"][f"{memory_type}:{operation_name}"].append(memory_delta)

    def optimize_memory_configuration(self, memory, usage_patterns: dict) -> dict:
        """Suggest optimizations based on usage patterns"""
        suggestions = []

        # Analyze operation frequencies
        frequent_operations = [op for op, count in usage_patterns.items() if count > 100]

        # Suggest capacity adjustments
        if "retrieve" in frequent_operations and isinstance(memory, GroundedMemory):
            avg_retrieve_time = np.mean(self.metrics["operation_times"]["grounded:retrieve"])
            if avg_retrieve_time > 0.1:  # 100ms threshold
                suggestions.append({
                    "type": "capacity_reduction",
                    "reason": "Frequent retrieval operations are slow",
                    "suggestion": "Reduce semantic_threshold from 3 to 2"
                })

        # Suggest caching strategies
        cache_hit_rate = (self.metrics["cache_hits"]["total"] /
                         (self.metrics["cache_hits"]["total"] + self.metrics["cache_misses"]["total"]))

        if cache_hit_rate < 0.7:
            suggestions.append({
                "type": "caching_improvement",
                "reason": f"Cache hit rate is {cache_hit_rate:.2%}",
                "suggestion": "Implement context caching for frequent queries"
            })

        return {
            "performance_metrics": self.get_performance_summary(),
            "optimization_suggestions": suggestions
        }

# Usage example
monitor = MemoryPerformanceMonitor()
memory = create_memory("grounded")

# Monitor operations
with monitor.measure_operation("add_interaction", "grounded"):
    memory.add_interaction("Hello", "Hi there!")

with monitor.measure_operation("get_context", "grounded"):
    context = memory.get_full_context("greeting")

# Get optimization suggestions
suggestions = monitor.optimize_memory_configuration(memory, {"add_interaction": 500, "get_context": 200})
```

These usage patterns demonstrate how AbstractMemory can be applied across different scenarios, from simple task agents to sophisticated learning systems. The key is choosing the right memory type for your agent's complexity and leveraging the appropriate patterns for your specific use case.