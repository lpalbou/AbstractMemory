

# **Deconstructing the ReAct Scratchpad: A Technical Guide to Context and State Management in LLM Agents**

## **Section 1: The ReAct Paradigm and the Foundational Role of the Scratchpad**

The development of agentic systems powered by Large Language Models (LLMs) represents a significant shift from conversational AI to goal-oriented problem-solving. Central to this evolution is the ReAct paradigm, an architectural pattern that enables LLMs to reason and interact with external environments to accomplish complex tasks. This report provides a definitive technical deconstruction of the ReAct scratchpad, the core component that facilitates this architecture. It will move beyond conceptual overviews to dissect the specific mechanics of the scratchpad's construction, the precise flow of information within an agent's context, and its critical relationship with persistent conversational history. The analysis will be grounded in concrete, step-by-step examples and technical details from established frameworks, offering an implementation-focused guide for developers and researchers building robust AI agents.

### **1.1 Synergizing Reasoning and Acting**

The ReAct (Reason+Act) framework is a general paradigm designed to enable LLMs to solve complex tasks by interleaving verbal reasoning traces with task-specific actions.1 This approach was developed to synergize two distinct but complementary capabilities of LLMs: their capacity for reasoning, as demonstrated by techniques like Chain-of-Thought (CoT) prompting, and their ability to generate actions, such as API calls or tool usage.2 The core principle of ReAct is that reasoning and acting are mutually beneficial. The synergy allows an agent to engage in a dynamic feedback loop: it can "reason to act," where internal deliberation is used to create, maintain, and adjust high-level plans, and it can "act to reason," where interactions with external environments (e.g., a Wikipedia API, a database) provide new information that is incorporated back into the reasoning process.3  
This interleaved process directly addresses the inherent limitations of antecedent techniques. Pure CoT prompting, while effective for tasks requiring multi-step logic, operates solely within the model's internal knowledge and is prone to fact hallucination and error propagation.2 Conversely, early action-oriented models often lacked the sophisticated planning and exception-handling capabilities needed for complex, long-horizon tasks. ReAct bridges this gap by grounding the model's reasoning in external observations. By forcing the model to verify its hypotheses and gather new data through actions, the framework improves the factuality, groundedness, and trustworthiness of the agent's outputs.4 This tight integration of reasoning and acting produces human-aligned, interpretable task-solving trajectories, enhancing both performance and diagnosability.1

### **1.2 The Scratchpad: The Agent's Working Memory**

The primary architectural challenge in building any multi-step agent with an LLM is the stateless nature of the underlying model. Standard LLM API calls are independent transactions; the model has no built-in memory of previous interactions within a single task execution. An agent's ability to make a decision at step N is entirely dependent on having the context of steps 1 through N−1 provided in the prompt for step N. The ReAct scratchpad is the definitive architectural solution to this fundamental problem. It functions as an ephemeral, short-term working memory that is meticulously constructed and maintained by an external orchestration system.7  
The scratchpad is not merely a passive log for human inspection; it is the active, primary mechanism for maintaining state and context throughout the Thought-Action-Observation loop. At each turn, the entire history of the current task-solving attempt—every thought, every action taken, and every observation received—is formatted into the scratchpad and passed back to the LLM. This process simulates a continuous, stateful reasoning process on top of a stateless computational engine.8  
Fundamentally, the ReAct scratchpad is the concrete implementation of state management for a reasoning engine that is inherently stateless. An LLM's function can be described as f(prompt)→completion. To enable a sequence of dependent decisions, the prompt for each subsequent call must contain the history of the prior decisions and their outcomes. The scratchpad is the data structure that programmatically collects and formats this history (e.g., Thought 1, Action 1, Observation 1, Thought 2,...). Therefore, the iterative loop of (current\_context \+ scratchpad) \-\> LLM \-\> new\_thought\_action \-\> execute \-\> (current\_context \+ scratchpad \+ new\_observation) constitutes the fundamental algorithm of a ReAct agent. The scratchpad serves as the accumulator variable in this algorithm, making the management of the LLM's context window a primary, not secondary, engineering concern.

## **Section 2: The Anatomy and Programmatic Construction of the Scratchpad**

The functionality of the ReAct framework is contingent upon a well-defined structure for the scratchpad and a robust orchestration system to manage it. The scratchpad's content is generated through a collaboration between the LLM, which produces the reasoning and action specifications, and an external system, which executes actions and appends the results. This section provides a deep dive into the canonical structure of the scratchpad and the programmatic loop required for its construction.

### **2.1 The Core Triad: Thought, Action, Observation**

The ReAct scratchpad is built from a repeating sequence of three distinct elements, each serving a specific role in the agent's cognitive cycle.

* **Thought:** This is the LLM's internal reasoning trace, generated in unstructured natural language. It serves as the "inner monologue" of the agent, where it verbalizes its understanding of the problem, decomposes the main goal into sub-tasks, formulates a plan, reflects on the results of previous actions, and handles exceptions.1 The  
  Thought component is the explicit "reasoning" part of the ReAct paradigm and is crucial for interpretability, allowing developers to trace the agent's decision-making process.1  
* **Action:** Following a Thought, the LLM generates a structured, parseable command to interact with an external tool. This is the "acting" part of the framework. The action is typically formatted in a specific syntax, most commonly ToolName\[input\], to facilitate easy parsing by the orchestration logic.4 For example,  
  Search\[Colorado orogeny\] instructs the system to use the Search tool with the query "Colorado orogeny." The set of available tools and their required input formats are defined in the agent's initial prompt.  
* **Observation:** This element represents the feedback from the external environment. After the orchestration system parses an Action and executes the corresponding tool, the tool's return value (e.g., an API response, a database query result, a calculation) is formatted as an Observation and appended to the scratchpad.7 This information is then available to the LLM in the next cycle, grounding its subsequent  
  Thought in empirical data from the environment.

### **2.2 The Orchestration Loop: The System Behind the Scratchpad**

A critical concept to understand is the division of labor in a ReAct system. The LLM is the **reasoning engine**, responsible only for generating the text corresponding to Thought and Action. The surrounding application code, often managed by a framework like LangChain or LangGraph, serves as the **execution engine** and **state manager**. This orchestrator is responsible for the programmatic loop that builds the scratchpad.  
The orchestration loop proceeds through the following steps:

1. **Prompt Construction:** The orchestrator assembles the initial, complete prompt to be sent to the LLM. This includes a system prompt with instructions, definitions of available tools, any few-shot examples, the user's query, and the existing conversational chat history.  
2. **LLM Invocation:** The complete prompt is sent to the LLM via an API call.  
3. **Output Parsing:** The orchestrator receives the LLM's text completion. It must then parse this output to separate the natural language Thought from the structured Action string. Regular expressions or other string-parsing methods are typically used for this step.  
4. **Tool Dispatch and Execution:** The Action string is further parsed to identify the tool name and its input argument. The orchestrator then calls the corresponding function or method in the application code, passing the extracted input.  
5. **Scratchpad Append:** The value returned by the tool is formatted into an Observation string. The full Thought-Action-Observation triad is then appended to the existing scratchpad data structure.  
6. **Loop or Terminate Condition:** The orchestrator checks the LLM's last output. If the action was a special Finish\[answer\] or Final Answer command, the loop terminates. Otherwise, the process repeats from step 2, but this time the prompt sent to the LLM includes the newly updated and expanded scratchpad.

### **2.3 Prompting Strategies to Define Scratchpad Structure**

The LLM must be instructed on how to generate outputs in the required Thought-Action-Observation format. This is achieved through prompt engineering, primarily using two strategies.

* **Zero-Shot Prompting:** This approach relies on the instruction-following capabilities of modern LLMs. The system prompt contains explicit, detailed instructions that describe the ReAct cycle and the required output format. No concrete examples are provided; the model is expected to understand and follow the abstract rules.10 A typical zero-shot instruction might be: "You must solve problems using the ReAct approach. For each step, follow the format:  
  Thought: Reason step-by-step about the current situation. Action: The specific action to take from the available tools. Observation: The result of the action. Continue this cycle until you have the final answer.".10  
* **Few-Shot Prompting:** This technique involves including one or more complete, hard-coded examples of a full Thought-Action-Observation trajectory within the initial prompt.4 These exemplars provide a powerful, concrete pattern for the LLM to imitate. This method is particularly effective for ensuring adherence to a specific format, guiding the model on complex or nuanced tasks, or for use with models that have weaker instruction-following abilities.6 The examples demonstrate not only the format but also the desired style and depth of reasoning for the  
  Thought component.

## **Section 3: The ReAct Cycle in Action: A Granular Walkthrough**

To fully grasp the mechanics of the scratchpad, it is essential to trace its construction step-by-step. This section provides a granular, turn-by-turn analysis of a ReAct agent solving a multi-hop question, showing the exact content of the LLM's context and the state of the scratchpad at the beginning and end of each cycle. The task is based on an example from the original ReAct research: "What is the elevation range for the area that the eastern sector of the Colorado orogeny extends into?".6

### **3.1 Initial State (Start of Cycle 1): The Full Context**

Before the first Thought is generated, the orchestration framework assembles a comprehensive prompt. This initial context is the complete input for the first LLM call and does not yet contain a scratchpad, as no steps have been taken.  
**Content Sent to LLM:**

1. **System Prompt:** This section contains the core instructions for the agent.  
   * **Role and Goal:** "You are an agent designed to answer questions by reasoning and interacting with a set of tools."  
   * **Tool Definitions:** "Available tools: Search\[query\]: Searches a knowledge base for information on the query. Lookup\[keyword\]: Looks up a specific keyword in the last search result. Finish\[answer\]: Submits the final answer to the user."  
   * **Format Instructions (Zero-Shot):** "You must operate in a Thought, Action, Observation cycle. After your final thought, use the Finish tool."  
   * **Few-Shot Examples:** (For robustness, a few-shot example would be included here, demonstrating a full trajectory for a different question).  
2. **Chat History:** For this example, we assume the conversation is new, so this section is empty.  
3. **Current User Query:**  
   Question: What is the elevation range for the area that the eastern sector of the Colorado orogeny extends into?

4. **Initiation Prompt:** A final string to prompt the model to begin its reasoning process.  
   Thought:

### **3.2 Cycle 1: Building the First Scratchpad Entry**

The LLM receives the context from Section 3.1 and generates its first reasoning step and action.

* LLM Generates (Completion):  
  I need to search Colorado orogeny, find the area that the eastern sector of the Colorado orogeny extends into, then find the elevation range of the area.  
  Action: Search\[Colorado orogeny\]  
* **Orchestrator Action:**  
  1. Parses the completion, separating the Thought from the Action.  
  2. Identifies the tool as Search and the input as "Colorado orogeny".  
  3. Executes the Search tool.  
* Tool Returns (Result):  
  The Colorado orogeny was an episode of mountain building (an orogeny) in Colorado and surrounding areas.  
* Scratchpad State at End of Cycle 1: The orchestrator formats the tool's result as an Observation and constructs the first entry in the scratchpad.  
  Thought: I need to search Colorado orogeny, find the area that the eastern sector of the Colorado orogeny extends into, then find the elevation range of the area.  
  Action: Search\[Colorado orogeny\]  
  Observation: The Colorado orogeny was an episode of mountain building (an orogeny) in Colorado and surrounding areas.

### **3.3 Cycle 2: The Feedback Loop in Action**

For the second turn, the scratchpad is now a critical part of the LLM's context, providing the memory of the first step.

* **Context for LLM (Start of Cycle 2):** The prompt for the second LLM call is the *entire* initial context from Section 3.1, with the full scratchpad from the end of Cycle 1 appended before the final Thought: initiation prompt.  
  Question: What is the elevation range for the area that the eastern sector of the Colorado orogeny extends into?

  Thought: I need to search Colorado orogeny, find the area that the eastern sector of the Colorado orogeny extends into, then find the elevation range of the area.  
  Action: Search\[Colorado orogeny\]  
  Observation: The Colorado orogeny was an episode of mountain building (an orogeny) in Colorado and surrounding areas.

  Thought:

* LLM Generates (Completion):  
  It does not mention the eastern sector. So I need to look up eastern sector.  
  Action: Lookup\[eastern sector\]  
* **Orchestrator Action:** Executes the Lookup tool on the previous search result.  
* Tool Returns (Result):  
  The eastern sector extends into the High Plains and is called the Central Plains orogeny.  
* Scratchpad State at End of Cycle 2: The new Thought-Action-Observation triad is appended to the scratchpad.  
  Thought: I need to search Colorado orogeny, find the area that the eastern sector of the Colorado orogeny extends into, then find the elevation range of the area.  
  Action: Search\[Colorado orogeny\]  
  Observation: The Colorado orogeny was an episode of mountain building (an orogeny) in Colorado and surrounding areas.  
  Thought: It does not mention the eastern sector. So I need to look up eastern sector.  
  Action: Lookup\[eastern sector\]  
  Observation: The eastern sector extends into the High Plains and is called the Central Plains orogeny.

This iterative process continues. The agent will next reason that it needs to find the elevation of the "High Plains," leading to further Search actions. At each step, the scratchpad grows, providing an ever-richer context of the task's history. The loop concludes only when the LLM generates a final Thought summarizing its findings and an Action: Finish\[1,800 to 7,000 ft\].6 At that point, the orchestration loop terminates.

## **Section 4: Context Integration: The Scratchpad and the Global Chat History**

A frequent point of confusion in agent architecture is the distinction between the agent's working memory for a specific task and the long-term memory of the overall conversation. ReAct agents operate with two distinct but related memory systems: the ephemeral ReAct scratchpad and the persistent global chat history. Understanding their separate lifecycles, content, and purposes is crucial for effective agent design and state management.

### **4.1 The Lifecycle of the Scratchpad: Create, Append, Discard**

The ReAct scratchpad is fundamentally ephemeral. Its existence is tied directly to the execution of a single agentic task.

* **Creation:** A new, empty scratchpad is instantiated at the moment the agent is invoked to solve a user's query.  
* **Growth:** The scratchpad grows additively with each Thought-Action-Observation cycle, accumulating the entire execution trace for the current task. It persists in memory only for the duration of this execution loop.  
* **Termination:** Once the LLM generates a terminal action, such as Finish\[answer\], the orchestration loop concludes. At this point, the scratchpad has fulfilled its purpose as the short-term memory for that specific task. It is not automatically appended to any long-term storage and is effectively discarded.11 Its contents represent the "how" of the answer, not the answer itself.

### **4.2 Condensing the Trajectory for Persistent History**

The global chat history serves a different purpose: to maintain the context of the conversation between the user and the agent over multiple turns.12 It is designed to be a clean, human-readable dialogue log, not a verbose execution trace. Therefore, the raw contents of the scratchpad are unsuitable for direct inclusion.  
Upon the termination of a ReAct loop, the orchestration framework performs a condensation step:

1. The final answer is extracted from the terminal action (e.g., the string "The capital of France is Paris." from Finish).  
2. The orchestrator creates a clean, structured message object (e.g., an AIMessage in LangChain) containing only this final answer.  
3. This message, paired with the user's initial query (e.g., a HumanMessage), is what gets appended to the persistent global chat history. This history can be stored in various backends, from a simple in-memory list to a persistent database like SQLite or Postgres, enabling conversations that span multiple sessions.13

This separation is a deliberate architectural choice. ReAct agents operate with two distinct memory systems that serve different purposes and operate on different timescales. The **Global Chat History** provides *conversational context*, informing the agent's initial understanding of a new query by showing what has been discussed before. The **Scratchpad** provides *task-oriented context*, enabling the agent's immediate, step-by-step reasoning by logging what it has just done and learned.  
Consider a follow-up user query: "What about for the western sector?" To answer this, the agent needs to know the context of the previous question about the "eastern sector." This information is retrieved from the **Global Chat History**. Armed with this conversational context, the agent then begins a *new* ReAct loop to solve this specific task, creating a *new, empty* **Scratchpad**. The agent's first step within this new scratchpad might be Thought: The user is asking a follow-up question about the Colorado orogeny. I need to find information on the western sector.... This demonstrates a clear division of labor: the chat history provides the background for the entire task, while the scratchpad manages the state for the current execution trace. Modern frameworks like LangGraph explicitly model this separation, using persistent checkpointers to manage the global chat history while the in-memory graph state serves as the scratchpad for the current run.15

### **4.3 Context Flow Comparison**

The following table summarizes the key distinctions between the ReAct scratchpad and the global chat history, clarifying their unique roles in the agent's architecture. This comparison highlights how the two systems work in concert to provide both short-term reasoning capability and long-term conversational memory.

| Feature | ReAct Scratchpad | Global Chat History |
| :---- | :---- | :---- |
| **Purpose** | Short-term working memory for a single task execution loop. Enables iterative reasoning. | Long-term memory of the entire conversation across multiple turns and agent invocations. |
| **Lifecycle** | Ephemeral: Created on agent invocation, discarded on task completion (Final Answer). | Persistent: Maintained for the duration of a user session (or longer, if persisted). |
| **Content** | Raw, verbose execution trace: Thought, Action, Observation steps. Machine-oriented. | Clean, user-facing dialogue: A sequence of user queries and the agent's final answers. |
| **Format** | Often a single, growing string or a list of raw text blocks. | A structured list of message objects (e.g., HumanMessage, AIMessage, SystemMessage). |
| **LLM Visibility** | The full, growing scratchpad is passed into the LLM context at *every step* of the loop. | Passed into the LLM context *once* at the beginning of an agent loop to provide conversational context. |
| **Example** | Thought: I need to find X. Action: Search\[X\] Observation: X is Y. | user: "What is X?", assistant: "X is Y." |

## **Section 5: Advanced Context Management and Framework Implementations**

While the additive nature of the scratchpad is essential for maintaining state, it introduces a significant engineering challenge: the LLM's finite context window. For complex tasks that require numerous Thought-Action-Observation cycles, the scratchpad can grow to exceed the token limit of the model, leading to a catastrophic failure where the agent effectively loses its own short-term memory. This section explores advanced strategies for managing scratchpad size and examines how modern agentic frameworks provide tools to implement these solutions.

### **5.1 The Context Window Constraint**

At each step of the ReAct loop, the entire scratchpad is sent back to the LLM. If a task requires 10 steps, the context for the 10th step will contain the full text of the previous nine Thought-Action-Observation triads. As this text accumulates, it consumes an increasing number of tokens. When the total length of the prompt (including system instructions, tools, chat history, and the scratchpad) exceeds the model's context window (e.g., 8,192 or 128,000 tokens), the API call will fail. More insidiously, if the context is truncated improperly, the agent will lose crucial information from its earliest reasoning steps, derailing its ability to complete the task coherently.15 Managing this growing context is therefore a non-negotiable aspect of building robust ReAct agents.

### **5.2 Strategies for Context Management**

Several strategies can be employed to prevent context overflow, each with its own trade-offs in terms of computational cost, latency, and potential information loss.

* **Trimming:** This is the most straightforward strategy. When the context approaches its limit, the oldest messages or Thought-Action-Observation turns are removed from the scratchpad to create space for new ones. Common trimming approaches include removing the first N messages ("first-in, first-out") or the last N messages. For instance, LangChain provides a trim\_messages utility that can be configured with a strategy="last" or strategy="first" parameter.15 While simple and computationally cheap, this method carries a significant risk of discarding crucial early context that may be necessary for the final answer.  
* **Summarization:** A more sophisticated approach involves using an LLM to create a condensed summary of the oldest parts of the scratchpad. Instead of simply deleting the early turns, they are replaced with a natural language summary that preserves their semantic essence while using far fewer tokens. For example, the first five T-A-O cycles could be replaced with a single message like: "Summary of early steps: I determined the user's query is about the Colorado orogeny, searched for initial information, and found that its eastern sector extends into the High Plains." This preserves context but introduces the additional latency and cost of a separate LLM call for the summarization task.15

### **5.3 Implementation with Hooks and Frameworks**

Modern agent frameworks provide elegant mechanisms for implementing these context management strategies. LangGraph, a library for building stateful, multi-actor applications, is particularly well-suited for this. It allows developers to define a pre\_model\_hook function that intercepts and modifies the agent's state just before it is passed to the LLM.15  
This hook is the ideal location to implement trimming or summarization logic. The function can inspect the current state (which contains the full, unabridged scratchpad), check its token count, and if necessary, apply a reduction strategy. Crucially, this can be done in a way that modifies only the input being sent to the LLM, while the full, untruncated scratchpad is preserved in the agent's persistent state. This allows the agent to maintain a complete record of its history while still operating within the LLM's context limits.15  
Furthermore, LangGraph's explicit state management, using constructs like StateGraph and MessagesState, formalizes the concept of the scratchpad.13 The  
messages list within the AgentState object *is* the scratchpad. The framework's nodes (e.g., call\_model, tool\_node) and conditional edges (e.g., should\_continue) represent the orchestration loop, programmatically managing the flow of information into and out of this state object.17 This graph-based approach provides a more transparent, robust, and customizable architecture for managing the scratchpad compared to older, monolithic agent executors.

## **Section 6: Comparative Analysis: ReAct, Self-Ask, and Other Reasoning Techniques**

The ReAct scratchpad is a specific implementation of agent memory, but it exists within a broader landscape of reasoning techniques. By comparing it to related methods like Chain-of-Thought and Self-Ask, its unique architectural contributions become clearer. These techniques are not mutually exclusive competitors but rather points on a spectrum of agent design, where the complexity of the scratchpad and its orchestration logic scales with the required capabilities of the agent.

### **6.1 ReAct vs. Chain-of-Thought (CoT)**

Chain-of-Thought prompting is the foundation upon which more complex reasoning patterns are built. In a CoT prompt, the LLM is simply instructed to "think step-by-step" before providing a final answer.1 The "scratchpad" in this context is implicit; it is merely the continuous stream of text that constitutes the model's reasoning process. There is no interaction with an external environment. The key innovation of ReAct is to structure this reasoning process and ground it in reality. It transforms the scratchpad from a passive monologue into an interactive log of thoughts and experiments. The inclusion of the  
Action and Observation components forces the reasoning to be validated against external information, mitigating hallucination and making the agent's conclusions more reliable.6

### **6.2 ReAct vs. Self-Ask**

Self-Ask is another advanced prompting technique that structures the reasoning process. In Self-Ask, the LLM is prompted to explicitly decompose a complex question into a series of simpler, follow-up sub-questions. It then answers each sub-question, often by calling an external tool like a search engine, before synthesizing a final answer.21  
The primary difference lies in the structure and flexibility of the reasoning component. The Self-Ask "scratchpad" is highly structured, following a rigid Follow up: \[sub-question\] \-\> Intermediate answer: \[result from tool\] pattern.21 This is extremely effective for compositional question-answering tasks that can be neatly broken down. ReAct, by contrast, is more general-purpose. Its  
Thought component is free-form natural language, allowing the agent to engage in more complex cognitive tasks beyond simple decomposition, such as high-level planning, progress tracking, exception handling, and dynamic plan adjustment based on unexpected observations.20 While Self-Ask grounds each sub-question independently with a tool call, ReAct's reasoning is grounded in the  
Observation from the *previous* step, creating a tighter, more iterative feedback loop that is better suited for dynamic and unpredictable environments.20  
This comparison reveals an evolution in the role and complexity of the scratchpad. In CoT, it is a passive transcript of thought. In Self-Ask, it becomes a structured dialogue the model has with itself to solve a problem. In ReAct, it matures into an active, interactive log of a dynamic process of hypothesis and experimentation. The choice of technique dictates the required complexity of the scratchpad's data structure and the sophistication of the orchestration logic needed to manage it.

## **Conclusion**

The ReAct scratchpad is far more than a simple logging mechanism; it is the central architectural component that enables a stateless Large Language Model to function as a stateful, goal-oriented agent. By providing a structured, ephemeral working memory, the scratchpad allows the agent to maintain context, track progress, and integrate external information throughout the iterative Thought-Action-Observation cycle. Its programmatic construction and management by an external orchestrator represent a fundamental division of labor, where the LLM serves as the reasoning engine and the surrounding framework acts as the execution and state management layer.  
A clear distinction must be drawn between the ephemeral, task-oriented scratchpad and the persistent, conversational global chat history. The scratchpad captures the raw, verbose execution trace of a single task and is discarded upon completion. The chat history stores a clean, user-facing dialogue of queries and final answers, providing long-term conversational context. This dual-memory system is essential for building agents that are both effective problem-solvers and coherent conversational partners.  
As agentic tasks grow in complexity, the engineering challenges associated with managing the scratchpad, particularly the constraint of the LLM's context window, become paramount. Advanced techniques such as message trimming and summarization, implemented through hooks in modern frameworks like LangGraph, are critical for ensuring the stability and scalability of ReAct agents. Ultimately, the design of the scratchpad and its corresponding orchestration logic exists on a spectrum, from the simple monologue of Chain-of-Thought to the highly structured, interactive log of ReAct. The sophistication of this mechanism directly reflects the cognitive capabilities of the agent, positioning the scratchpad as a cornerstone of modern agentic AI architecture.

#### **Works cited**

1. ReAct: Synergizing Reasoning and Acting in Language Models, accessed September 15, 2025, [https://research.google/blog/react-synergizing-reasoning-and-acting-in-language-models/](https://research.google/blog/react-synergizing-reasoning-and-acting-in-language-models/)  
2. ReAct: Synergizing Reasoning and Acting in Language Models \- ResearchGate, accessed September 15, 2025, [https://www.researchgate.net/publication/364290390\_ReAct\_Synergizing\_Reasoning\_and\_Acting\_in\_Language\_Models](https://www.researchgate.net/publication/364290390_ReAct_Synergizing_Reasoning_and_Acting_in_Language_Models)  
3. ReAct: Synergizing Reasoning and Acting in Language Models \- arXiv, accessed September 15, 2025, [https://arxiv.org/pdf/2210.03629](https://arxiv.org/pdf/2210.03629)  
4. ReAct Prompting: How We Prompt for High-Quality Results from ..., accessed September 15, 2025, [https://www.width.ai/post/react-prompting](https://www.width.ai/post/react-prompting)  
5. ReAct: Synergizing Reasoning and Acting in Language Models \- Summary \- Portkey, accessed September 15, 2025, [https://portkey.ai/blog/react-synergizing-reasoning-and-acting-in-language-models-summary/](https://portkey.ai/blog/react-synergizing-reasoning-and-acting-in-language-models-summary/)  
6. ReAct \- Prompt Engineering Guide, accessed September 15, 2025, [https://www.promptingguide.ai/techniques/react](https://www.promptingguide.ai/techniques/react)  
7. Implementing AI agents from Scratch using Langchain and OpenAI \- GeekyAnts, accessed September 15, 2025, [https://geekyants.com/blog/implementing-ai-agents-from-scratch-using-langchain-and-openai](https://geekyants.com/blog/implementing-ai-agents-from-scratch-using-langchain-and-openai)  
8. What is a ReAct Agent? | IBM, accessed September 15, 2025, [https://www.ibm.com/think/topics/react-agent](https://www.ibm.com/think/topics/react-agent)  
9. Using LangChain ReAct Agents to Answer Complex Questions \- Airbyte, accessed September 15, 2025, [https://airbyte.com/data-engineering-resources/using-langchain-react-agents](https://airbyte.com/data-engineering-resources/using-langchain-react-agents)  
10. Comprehensive Guide to ReAct Prompting and ReAct based Agentic Systems \- Mercity AI, accessed September 15, 2025, [https://www.mercity.ai/blog-post/react-prompting-and-react-based-agentic-systems](https://www.mercity.ai/blog-post/react-prompting-and-react-based-agentic-systems)  
11. Agents \- Docs by LangChain, accessed September 15, 2025, [https://docs.langchain.com/oss/python/langchain/agents](https://docs.langchain.com/oss/python/langchain/agents)  
12. Chat history \- ️ LangChain, accessed September 15, 2025, [https://python.langchain.com/docs/concepts/chat\_history/](https://python.langchain.com/docs/concepts/chat_history/)  
13. How to add chat history | 🦜️ LangChain, accessed September 15, 2025, [https://python.langchain.com/docs/how\_to/qa\_chat\_history\_how\_to/](https://python.langchain.com/docs/how_to/qa_chat_history_how_to/)  
14. LangChain: Building a local Chat Agent with Custom Tools and Chat History \- Admantium, accessed September 15, 2025, [https://admantium.com/blog/llm25\_langchain\_agent\_with\_chat\_history/](https://admantium.com/blog/llm25_langchain_agent_with_chat_history/)  
15. How to manage conversation history in a ReAct Agent \- GitHub Pages, accessed September 15, 2025, [https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-manage-message-history/](https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-manage-message-history/)  
16. Build an Agent \- ️ LangChain, accessed September 15, 2025, [https://python.langchain.com/docs/tutorials/agents/](https://python.langchain.com/docs/tutorials/agents/)  
17. How to create a ReAct agent from scratch \- GitHub Pages, accessed September 15, 2025, [https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/](https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/)  
18. Prompt Engineering: Advanced Techniques \- MLQ.ai, accessed September 15, 2025, [https://blog.mlq.ai/prompt-engineering-advanced-techniques/](https://blog.mlq.ai/prompt-engineering-advanced-techniques/)  
19. 5 Advanced Prompting Techniques to Improve Your LLM App's Responses \- athina.ai, accessed September 15, 2025, [https://blog.athina.ai/5-advanced-prompting-techniques-to-improve-your-llm-app-s-responses](https://blog.athina.ai/5-advanced-prompting-techniques-to-improve-your-llm-app-s-responses)  
20. Evolving Language Model Prompting: Prompting Strategies for Enhanced Language Model Performance (part 2\) | by David Gutsch | Medium, accessed September 15, 2025, [https://medium.com/@david.gutsch0/evolving-language-model-prompting-prompting-strategies-for-enhanced-language-model-performance-3352172e0d60](https://medium.com/@david.gutsch0/evolving-language-model-prompting-prompting-strategies-for-enhanced-language-model-performance-3352172e0d60)  
21. Self-Ask Prompting: Improving LLM Reasoning with Step-by-Step Question Breakdown, accessed September 15, 2025, [https://learnprompting.org/docs/advanced/few\_shot/self\_ask](https://learnprompting.org/docs/advanced/few_shot/self_ask)  
22. Measuring and Narrowing the Compositionality Gap in Language ..., accessed September 15, 2025, [https://arxiv.org/pdf/2210.03350](https://arxiv.org/pdf/2210.03350)  
23. ReAct Prompting vs. Self-Ask Prompting: Advanced Techniques in Language Models | by P-A Caillaud | Medium, accessed September 15, 2025, [https://medium.com/@CaillaudPA/react-prompting-vs-self-ask-prompting-advanced-techniques-in-language-models-000634f0d5a5](https://medium.com/@CaillaudPA/react-prompting-vs-self-ask-prompting-advanced-techniques-in-language-models-000634f0d5a5)