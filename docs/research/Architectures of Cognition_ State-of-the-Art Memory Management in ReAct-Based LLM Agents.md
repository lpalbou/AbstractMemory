

# **Architectures of Cognition: State-of-the-Art Memory Management in ReAct-Based LLM Agents**

## **Introduction**

### **Framing the Challenge: The Convergence of Agentic Reasoning and Computational Constraints**

The field of artificial intelligence is undergoing a significant paradigm shift, moving beyond the capabilities of static, single-turn Large Language Models (LLMs) toward the development of dynamic, autonomous AI agents. These agentic systems are designed to tackle complex, real-world challenges by emulating human-like cognitive processes such as planning, iterative reasoning, reflection, and interaction with external environments.1 Instead of merely generating text based on a fixed prompt, these agents can formulate and execute multi-step plans, adapt to new information, and leverage external tools to achieve specific goals with minimal human intervention.3 This evolution marks a critical step away from simple conversational bots and towards sophisticated problem-solving entities capable of orchestrating complex workflows.4  
At the heart of this transformation lies the challenge of memory. For an agent to reason effectively, it must maintain a coherent understanding of its task, the actions it has taken, the results of those actions, and the broader conversational context. This necessity of a rich, persistent memory, however, collides directly with fundamental computational and architectural constraints inherent in the Transformer models that power these agents.5 The very context window that serves as the agent's short-term memory becomes a performance bottleneck, where the processes of integrating new information and generating subsequent steps slow down dramatically as the history grows.6 This creates a central tension: the drive for greater cognitive capability through comprehensive memory is fundamentally at odds with the need for efficient, scalable, and responsive computation.

### **The ReAct Paradigm: A Primer on Iterative Reasoning and Action**

A seminal framework that formalizes the structure of agentic behavior is ReAct, an acronym for "Reasoning and Acting".8 Introduced by Yao et al., ReAct synergizes the introspective, step-by-step problem-solving capabilities of Chain-of-Thought (CoT) prompting with the ability to interact with the external world through tools.4 This paradigm provides a structured, conceptual framework for building AI agents that can dynamically adjust their approach based on new information. It achieves this by orchestrating an agent's cognitive cycle into a formal, interleaved pattern of  
Thought \-\> Act \-\> Observation.4  
In this loop, the agent first generates a "thought," a verbalized reasoning trace that decomposes the task and plans the next step. Based on this thought, it performs an "action," which typically involves calling an external tool like a search engine, database, or API. Finally, it incorporates the output of that action as an "observation," which informs the next thought, thus creating a powerful feedback loop that mirrors human problem-solving.10 This iterative process allows the agent to ground its reasoning in real-world information, significantly reducing the propensity for hallucination and enhancing the accuracy and trustworthiness of its conclusions.4

### **Thesis: A Multi-Layered Approach to Memory Optimization is Essential for Scalable Agentic Systems**

The inherent verbosity of the ReAct cycle, where every thought, action, and observation is explicitly recorded in the context window to maintain state, rapidly accelerates the onset of performance degradation. Addressing this critical bottleneck is not a matter of finding a single "silver bullet" solution. This report posits that the development of robust, scalable, and efficient agentic systems necessitates a sophisticated, multi-layered strategy for memory management. Such a strategy must holistically integrate innovations across the entire technology stack. This includes foundational architectural improvements that attack the core computational complexity of attention mechanisms; algorithmic and software-level techniques for intelligent context engineering, such as Retrieval-Augmented Generation (RAG) and dynamic summarization; and the implementation of advanced memory architectures that intelligently manage a hierarchy of short-term and long-term memory stores. Only by combining these approaches can the tension between cognitive fidelity and computational efficiency be resolved, paving the way for the next generation of truly capable AI agents.

## **Part I: The Foundation of the Memory Bottleneck**

To fully appreciate the necessity and design of advanced memory management techniques, it is essential to first understand the fundamental architectural and practical limitations that create the performance bottleneck in LLM-based agents. The problem is not merely one of capacity but is deeply rooted in the computational principles of the Transformer architecture and the cognitive limitations of models when faced with extensive contexts.

### **1.1 The Quadratic Cost of Attention: A Technical Deep-Dive**

The revolutionary performance of modern LLMs is built upon the Transformer architecture, and its core innovation is the self-attention mechanism.12 This mechanism enables the model to weigh the importance of different tokens within an input sequence when producing a representation for each token, allowing it to capture complex, long-range dependencies.14

#### **The Self-Attention Mechanism**

In essence, for every token in the input sequence, self-attention calculates an "attention score" with respect to every other token in that same sequence. This process involves three learned matrices: Query (Q), Key (K), and Value (V), which are projections of the input token embeddings.12 The attention output for a given token is a weighted sum of the Value vectors of all tokens in the sequence, where the weights are determined by the compatibility between the token's Query vector and the Key vectors of all other tokens. The standard formulation for scaled dot-product attention is:  
Attention(Q,K,V)=softmax(dk​​QKT​)V  
Here, dk​ is the dimension of the key vectors, and the scaling factor dk​​1​ is used to prevent the dot products from growing too large and pushing the softmax function into regions with extremely small gradients.12

#### **Complexity Analysis**

The computational bottleneck arises from the matrix multiplication QKT. If the input sequence has a length of n tokens and the embedding dimension is d, the matrices Q and K have dimensions n×d. The transpose of K, KT, has dimensions d×n. The resulting multiplication, QKT, produces an n×n attention score matrix.15 Each element in this matrix represents the attention score between a pair of tokens in the sequence.  
This leads directly to a computational complexity that scales quadratically with the sequence length n.

* **Time Complexity:** The number of floating-point operations required to compute the n×n attention matrix is proportional to n2⋅d. Since d is typically a fixed hyperparameter for a given model, the dominant factor is n2. Therefore, the time complexity is expressed as O(n2).15 Doubling the length of the context window quadruples the computation time for the attention layer.  
* **Memory Complexity:** The n×n attention score matrix must be stored in memory to compute the gradients during training and for the subsequent multiplication with the V matrix. This results in a memory requirement that also scales quadratically, expressed as O(n2).17 This memory consumption can quickly exhaust the available VRAM on even high-end GPUs for long sequences.

#### **Hardware Implications**

These complexity characteristics have profound implications for real-world hardware performance. For relatively short context lengths, the process of loading the model's weights from high-bandwidth memory (HBM) into the GPU's faster on-chip SRAM is the primary bottleneck. In this regime, inference is said to be *memory-bandwidth-bound*.7 However, as the context length  
n increases, the quadratic growth in computation (n2) quickly outpaces the linear growth in memory access for the weights. The workload shifts from being memory-bound to being *compute-bound*. The sheer number of calculations required by the attention mechanism becomes the limiting factor, leading to a dramatic increase in latency (the time to generate the next token) and a decrease in throughput.7 This quadratic scaling is the fundamental, architectural root of the long-context problem.

### **1.2 The Long Context Dilemma: Practical Limitations Beyond Theory**

While hardware and computational complexity impose a hard ceiling on performance, a second, more subtle set of limitations emerges from the model's own cognitive behavior when processing long sequences. Recent advancements have led to models with astonishingly large advertised context windows, such as Google's Gemini 1.5 with up to 2 million tokens and Meta's Llama 4 with a 10 million token window.19 However, these figures often mask a more complex reality.

#### **Advertised vs. Usable Context**

There is a significant and well-documented gap between a model's *advertised* context length and its *effective* or *usable* context length.6 Empirical studies consistently show that while a model may be able to accept a very long input without crashing, its ability to reliably recall and reason over information within that context degrades substantially as the length increases. Performance on many tasks often becomes poor beyond approximately 100,000 tokens, at which point strategies like Retrieval-Augmented Generation (RAG) can become more effective than simply providing the full context.20 This discrepancy arises because the models are often not trained on sequences as long as their maximum theoretical length, leading to out-of-distribution challenges when they encounter such inputs at inference time.21

#### **The "Lost in the Middle" Phenomenon**

One of the most prominent failure modes in long-context models is a strong positional bias. Models demonstrate a U-shaped performance curve, where they can recall information presented at the very beginning and the very end of a long context with high accuracy, but struggle significantly to retrieve information that is "lost in the middle".20 This phenomenon undermines the naive assumption that a large context window functions like a perfect, randomly accessible memory. For an agentic system that builds a long history of thoughts and observations, critical information from early in the reasoning process can become effectively invisible to the model, leading to errors, repetition, or a complete breakdown in the task plan.

#### **Working Memory Bottleneck**

Further research indicates that the problem extends beyond simple information retrieval. Even when the context length is well within the model's advertised limits, its effective "working memory" can become overloaded. A study using a task that required models to track the state of multiple variables throughout a piece of code found that performance rapidly degraded to random guessing once the number of variables to track exceeded a small threshold (e.g., 5 to 10), far before the context window limit was reached.23  
This suggests that certain tasks, particularly those requiring complex reasoning like graph reachability, summarization of intricate documents, or logical deduction, have high working memory requirements. The Transformer architecture may struggle to maintain and update the intermediate representations needed for these tasks as the complexity of the input grows. This reveals a critical distinction: the context window is akin to the amount of paper one can have on a desk, while working memory is the cognitive capacity to actually process and synthesize the information on that paper. Simply adding more paper (a larger context window) does not increase cognitive capacity and can, in fact, degrade performance by introducing more noise and diluting the relevant signals needed to solve the task.5  
This dual crisis of computational cost and cognitive fidelity forms the complete picture of the memory bottleneck. The quadratic complexity of attention makes processing long contexts prohibitively expensive and slow. Simultaneously, even if the computational cost could be overcome, the model's inherent cognitive limitations—such as positional bias and a constrained working memory—prevent it from reliably using that extended context. An effective solution, therefore, must not only make long contexts computationally feasible but also structure the information within that context to align with the model's reasoning capabilities. The design of the ReAct cycle itself, with its verbose, iterative nature, directly collides with both of these constraints. Each loop of Think \-\> Act \-\> Observe appends a substantial amount of text to the context, rapidly consuming the available window and pushing the agent towards this performance cliff. Agentic workflows are thus "super-consumers" of context, and the more complex the reasoning required (i.e., the more loops), the more acute the memory pressure becomes, establishing a direct causal link between the agent's intelligence and its primary performance bottleneck.

## **Part II: Deconstructing the ReAct Cycle and Its Memory Footprint**

To design effective optimization strategies, it is crucial to first perform a granular analysis of how information flows into the context window during a standard ReAct cycle. This process reveals the precise nature and volume of data that contributes to context saturation and highlights the central role of the in-context "scratchpad" as the agent's working memory.

### **2.1 Anatomy of the Think \-\> Act \-\> Observe Loop: Information Flow and Content**

The ReAct loop is a stateful, iterative process where the output of one phase becomes the input for the next. The entire history of this process is typically maintained within the LLM's context window to ensure the agent has a complete record of its reasoning trajectory. Let us trace the information flow using a hypothetical user query: *"What was the revenue growth for Lyft in 2021 compared to Uber?"*

#### **Initiation (from Main Memory/User Query)**

The cycle begins when the agent receives the initial prompt from the user. This query forms the foundational content of the context window.  
**Context Window \- Start:**

User: What was the revenue growth for Lyft in 2021 compared to Uber?

#### **Phase 1: Think**

Upon receiving the prompt, the agent's first step is to reason about the task. The LLM is prompted to generate a natural language reasoning trace, often prefixed with a label like Thought:. This trace serves multiple purposes: it helps the model decompose the complex query into smaller, manageable sub-tasks; it allows the model to formulate a high-level plan; and it helps identify what information is missing and needs to be acquired.9 This entire block of text is appended to the context window.

* **Content:** A multi-sentence block of text detailing the agent's internal monologue. This might include breaking down the problem ("I need to find the 2021 and 2020 revenue for both Lyft and Uber to calculate the growth rate for each."), planning the sequence of actions ("First, I will search for Lyft's financial reports. Then, I will do the same for Uber."), and preparing for the next step.4  
* **Purpose:** To guide the agent's subsequent action and to create an explicit, auditable trail of its logic, which is invaluable for debugging and ensuring trustworthiness.4

**Context Window \- After Think:**

User: What was the revenue growth for Lyft in 2021 compared to Uber?  
Thought: The user wants to compare the revenue growth of Lyft and Uber for the year 2021\. To do this, I need to find the revenue for both companies for 2021 and 2020\. Then I can calculate the year-over-year growth for each and compare them. I will start by finding Lyft's revenue. I should search for their 2021 10-K filing, as it will contain official financial data.

#### **Phase 2: Act**

Guided by the preceding thought, the agent now decides on a concrete action to take. This is typically a structured output that invokes an external tool.9 The format is often a simple string or a JSON object that the agentic framework can parse and execute, such as  
Action: \[tool\_name(parameter)\].25 This action string is also appended to the context.

* **Content:** A concise, machine-parseable command. For our example, this would be a call to a search tool.  
* **Purpose:** To interface with the external environment and gather the factual information identified as necessary in the Think phase. This is how the agent overcomes the knowledge limitations of its static training data.

**Context Window \- After Act:**

... (previous content)...  
Action: search\[Lyft 2021 10-K revenue\]

#### **Phase 3: Observe**

The agentic framework executes the action (e.g., queries the search engine) and receives a result. This result, whether it's a snippet of text, a numerical value, or an API error message, is then fed back into the context, prefixed with a label like Observation:.10

* **Content:** The raw or pre-processed output from the tool execution. This could be a paragraph from a financial document, a JSON response from an API, or a simple "Tool execution failed" message.9  
* **Purpose:** To provide the agent with new information from the external world. This observation closes the feedback loop, serving as the primary input for the next Think phase. The agent will re-evaluate its plan and progress based on this new data, deciding whether to continue with its original plan, adjust its strategy, or formulate a final answer.4

**Context Window \- After Observe:**

... (previous content)...  
Observation: According to Lyft's 2021 10-K filing, the company reported revenue of $3.2 billion in 2021, an increase from $2.4 billion in 2020\.

This entire, now-expanded context is then passed back to the LLM to initiate the next Think phase (e.g., "Now that I have Lyft's data, I will calculate its growth rate and then proceed to find Uber's data."). This cycle repeats, with each Thought \-\> Act \-\> Observe triplet further extending the context window, until the agent determines it has sufficient information to provide a final answer.

### **2.2 The Agent Scratchpad: In-Context Working Memory**

The term "scratchpad" is often used to describe the mechanism by which agents manage this iterative process. It is crucial to understand that in the context of ReAct, the scratchpad is not a separate, specialized memory architecture. Rather, **the scratchpad is the portion of the LLM's own context window that is allocated to record the full, sequential history of the Think \-\> Act \-\> Observe trajectory for a given task**.4 It functions as the agent's short-term, in-context working memory, allowing it to "think out loud" or "show its work" as it progresses through a problem.27

#### **Lifecycle of Scratchpad Contents**

The information within the scratchpad has a specific lifecycle tied to the execution of a single, coherent task.

* **Append-Only:** During a task, information is strictly appended to the scratchpad. The full history of all previous thoughts, actions, and observations is passed back to the LLM in each subsequent step.25 This is essential for the agent to maintain a consistent line of reasoning and to learn from the outcomes of its previous actions.  
* **Ephemeral by Default:** The scratchpad is inherently volatile. Its contents exist only within the context of the current task execution. When the agent provides a final answer and a new task is initiated, the scratchpad is typically cleared. The memory is not persistent across different tasks or user sessions unless an explicit external memory system is implemented to save its contents.30

#### **Role in Explainability and Debugging**

The explicit and human-readable nature of the scratchpad is a cornerstone of the ReAct framework's utility. By externalizing the model's reasoning process into the context window, it transforms the agent's decision-making from an opaque process occurring within the model's internal activations into a transparent, auditable log.4 This has several profound benefits:

* **Explainability:** Users and developers can follow the agent's step-by-step logic, understanding precisely how it arrived at its conclusion. This builds trust and provides confidence in the agent's output.1  
* **Debugging:** When an agent fails or produces an incorrect result, the scratchpad provides an invaluable diagnostic tool. Developers can inspect the trajectory to pinpoint the exact step where the reasoning went awry—was it a flawed thought, an incorrect tool call, or a misinterpretation of an observation?.4  
* **Steerability:** In some advanced implementations, the scratchpad can be edited by a human-in-the-loop, allowing for correction of the agent's reasoning path mid-task.24

This mechanism, however, embodies a fundamental design trade-off. The very feature that makes ReAct so powerful and interpretable—its detailed, verbose reasoning trail stored in the scratchpad—is also the primary driver of the context window saturation and the associated performance degradation discussed in Part I. The more complex the problem, the more Think \-\> Act \-\> Observe steps are required, leading to a longer and more computationally expensive scratchpad. This creates a direct tension between the agent's reasoning fidelity and its operational efficiency, a central challenge that the strategies detailed in the following section aim to address.

## **Part III: The “Warm Start” Problem: Integrating Pre-existing Chat History**

The previous examples illustrate a ReAct cycle starting from a single user query—a "cold start." However, in many real-world applications, an agent is activated within an ongoing conversation that may already contain a substantial amount of history, potentially tens of thousands of tokens. This "warm start" scenario introduces a critical layer of complexity: how does the agent effectively utilize this large, pre-existing context while executing its reasoning loops?

### **3.1 Integrating Chat History into the ReAct Prompt**

When an agent with memory capabilities begins a new task, its first action is to load the relevant conversation history. This history is not treated as a separate entity but is directly integrated into the prompt that is sent to the LLM for the initial Think step.68

* **Mechanism of Integration:** Frameworks like LangChain and LlamaIndex provide memory modules (e.g., ConversationBufferMemory) that store the conversation as a structured list of messages.68 Before the first  
  Think step, the agent's prompt formatter combines the static ReAct instructions (describing the Think \-\> Act \-\> Observe format and available tools) with the entire loaded chat history.71 The new user query is then appended to this combined context.69 The final prompt sent to the LLM looks conceptually like this 68:  
  \<System Instructions for ReAct\>  
  \<Available Tools Description\>

  Current conversation:  
  Human: \<message 1\>  
  AI: \<message 2\>  
  Human: \<message 3\>

... (potentially 20k+ tokens of history)...

Human: \<new user query\>  
AI:  
\`\`\`

* **Role of History in Reasoning:** This complete history serves as the foundational context for the agent's entire reasoning process.73 During the  
  Think phase, the LLM leverages this history to understand user intent, recall previously established facts, and maintain conversational coherence. For example, if a user asks a follow-up question like, "What about for my city?", the agent must parse the preceding chat history to identify the city mentioned earlier. The pre-existing context is indispensable for the agent to make informed decisions about which tools to use and how to use them.71

### **3.2 The Compounding Effect on Context Size**

The integration of a large chat history directly impacts the memory footprint of the ReAct cycle. The pre-existing history forms a large, static base to which the dynamic, append-only scratchpad is added.

* **Chat History vs. Scratchpad:** It is crucial to distinguish between these two components. The **chat history** is the record of user-assistant interactions *before* the current ReAct task began. The **agent scratchpad** is the record of the Thought \-\> Act \-\> Observe steps for the *current* task.74  
* **Combined Context:** On every turn of the ReAct loop, the LLM is sent a prompt containing the **entire chat history PLUS the entire up-to-date scratchpad**. This means that if an agent starts with 20,000 tokens of chat history and performs three ReAct steps that add 1,500 tokens to the scratchpad, the final call to the LLM for that task will have a context of 21,500 tokens. This compounding effect makes naive context management untenable for any non-trivial task.75

### **3.3 Strategies for Managing the "Warm Start"**

The massive context created by a "warm start" makes the advanced memory optimization techniques discussed later in this report not merely beneficial, but absolutely essential for practical application. The strategies must be applied to the pre-existing chat history *before* or *during* the ReAct cycle.

* **Pre-emptive Summarization or Trimming:** The most common approach is to process the large chat history before it is injected into the ReAct prompt. Instead of passing all 20,000 tokens, a secondary LLM call can summarize the history, or a simple trimming rule can be applied to only keep the last N messages.48 This compressed history then serves as a more manageable base context for the agent's reasoning.  
* **Dynamic Management with Hooks:** Advanced frameworks like LangGraph allow for a pre\_model\_hook. This function is executed before every LLM call and can be programmed to dynamically manage the message history. For instance, it can check the total token count and, if it exceeds a threshold, automatically summarize or trim the oldest parts of the combined chat history and scratchpad.48  
* **Treating History as a Long-Term Memory Store:** A more sophisticated pattern is to treat the extensive chat history not as short-term context but as a queryable long-term memory. The history is stored in a vector database, and at the start of the agent's run, a retrieval step pulls only the most relevant past interactions based on the new user query. These retrieved snippets, rather than the full history, are then placed into the context window, ensuring the agent has the relevant background without suffering from context overload.68

In conclusion, handling a large pre-existing chat history is a core challenge in real-world agentic systems. The history is vital for contextual reasoning but creates immense pressure on the context window. This forces developers to move beyond simple, append-only memory and implement active context engineering strategies to ensure the agent remains both intelligent and efficient.

## **Part IV: A Taxonomy of Memory Optimization Strategies**

Addressing the dual challenges of quadratic computational cost and cognitive degradation in long-context agents requires a multi-pronged approach. The state-of-the-art encompasses a spectrum of solutions, ranging from fundamental modifications to the model's architecture to sophisticated software patterns for managing the flow of information. This section provides a systematic taxonomy of these optimization strategies.

### **4.1 Architectural Solutions: Mitigating the Core Bottleneck with Efficient Attention**

The most fundamental approach to solving the long-context problem is to directly attack its root cause: the O(n2) complexity of the self-attention mechanism. This research area focuses on creating new model architectures or computational algorithms that can process longer sequences with sub-quadratic scaling, thereby increasing the raw capacity of the context window.

#### **Exact Attention with Hardware Optimization**

It is possible to improve performance without altering the mathematical definition of attention. These methods compute the exact same output as standard attention but do so more efficiently by optimizing the way calculations are performed on the underlying hardware.

* **FlashAttention:** This is a highly influential I/O-aware algorithm that does not approximate attention. Instead, it restructures the computation to minimize the slow and energy-intensive data transfers between the GPU's large but slow High-Bandwidth Memory (HBM) and its small but fast on-chip SRAM. By fusing multiple steps of the attention calculation into a single GPU kernel and using techniques like tiling, FlashAttention avoids writing the large n×n attention matrix to HBM, significantly reducing memory overhead and yielding substantial speedups (up to 22x on a single attention layer for very long sequences) for both training and inference without any loss of accuracy.22

#### **Approximate Attention Mechanisms**

A large body of research has focused on developing approximations of the full attention matrix that can be computed more efficiently. These methods trade a small amount of theoretical accuracy for significant gains in speed and memory efficiency.

* **Sparse Attention:** These techniques are based on the premise that most tokens only need to attend to a small, localized subset of other tokens to capture relevant context. By enforcing a sparse attention pattern, they avoid computing the full n×n matrix.  
  * **Longformer:** This model employs a combination of a sliding window attention pattern, where each token attends to a fixed number of neighboring tokens on either side, and a global attention pattern, where a few pre-selected tokens (like the \`\` token in BERT) are allowed to attend to all other tokens in the sequence. This combination captures both local context and long-range dependencies with a complexity of O(n), making it highly efficient for processing long documents.16  
  * **BigBird:** Similar to Longformer, BigBird uses a combination of sparse attention mechanisms to approximate full attention. It includes a set of global tokens, a local sliding window, and a random attention pattern where each token attends to a small, fixed number of random tokens. This combination has been shown to maintain the expressive power of full Transformers while scaling linearly with sequence length.16  
* **Linear Attention:** This family of methods aims to achieve O(n) complexity by reformulating the attention calculation to avoid the explicit construction of the n×n matrix.  
  * **Reformer:** This model uses Locality-Sensitive Hashing (LSH) to group similar tokens together into "buckets." Attention is then computed only within these smaller buckets, reducing the complexity from O(n2) to approximately O(nlogn).16  
  * **Kernel-Based Methods & HyperAttention:** Other linear methods approximate the softmax function using kernel methods or other mathematical tricks. For example, HyperAttention uses LSH to identify the most important ("heavy") entries in the attention matrix and computes an approximation based on those, achieving significant speedups, especially in settings that require causal masking for autoregressive generation.32

#### **Alternative Architectures**

Beyond modifying the Transformer, some research explores entirely new architectures that are inherently more efficient for sequential data.

* **State Space Models (SSMs):** Models like Mamba have emerged as strong competitors to Transformers. They are inspired by classical state space models from control theory and use a recurrence-like mechanism that allows them to process sequences with O(n) complexity. While they demonstrate impressive performance on long-context tasks, they represent a different architectural lineage and typically require training from scratch, making it difficult to apply their benefits to the vast ecosystem of existing pre-trained Transformer models.34

To provide a clear comparative overview for practitioners, the following table summarizes the key characteristics of these architectural approaches.  
**Table 1: Comparison of Efficient Attention Mechanisms**

| Mechanism | Key Methodology | Time Complexity | Memory Complexity | Key Advantage | Key Limitation |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Standard Attention** | Full QKT matrix multiplication for all token pairs. | O(n2) | O(n2) | Theoretically most expressive; captures all pairwise interactions. | Prohibitively expensive for long sequences. |
| **FlashAttention** | I/O-aware algorithm; avoids materializing the full attention matrix in HBM. | O(n2) | O(n) | Computes exact attention but is significantly faster and more memory-efficient in practice. | Still quadratically complex in computation; relies on specific hardware features. |
| **Sparse Attention (Longformer/BigBird)** | Combines local (sliding window) attention with sparse global connections. | O(n) | O(n) | Efficiently handles long documents while preserving some long-range dependencies. | Approximation may miss some complex, non-local relationships. |
| **Linear Attention (Reformer, etc.)** | Approximates the softmax computation using techniques like LSH or kernel methods. | O(nlogn) or O(n) | O(nlogn) or O(n) | Achieves linear or near-linear scaling, enabling very long sequences. | Approximation can lead to a loss of fidelity compared to exact attention. |
| **State Space Models (Mamba)** | Uses a recurrence-based mechanism inspired by control theory. | O(n) | O(n) | Highly efficient for both training and inference; excellent at long-range modeling. | Different architecture; cannot be easily applied to pre-trained Transformers. |

### **4.2 Externalizing Knowledge: Retrieval-Augmented Generation (RAG) as an Active Memory Tool**

Instead of attempting to fit all potentially relevant information into the model's finite context window from the start, Retrieval-Augmented Generation (RAG) offers a fundamentally different approach. In the context of agentic systems, RAG is best conceptualized not as a preprocessing step but as a powerful **tool** that the ReAct agent can dynamically invoke during its Act phase.36 This transforms memory access from a passive state of being into an active, on-demand process.

#### **The RAG Mechanism within a ReAct Loop**

The integration of RAG into the ReAct cycle follows a clear, three-stage process that aligns perfectly with the Think \-\> Act \-\> Observe structure.

1. **Indexing (Offline Preparation):** A large corpus of external knowledge—such as an organization's internal documentation, a set of technical manuals, or a snapshot of the web—is processed. The documents are broken down into smaller, manageable chunks. Each chunk is then passed through an embedding model to create a high-dimensional vector representation that captures its semantic meaning. These embeddings, along with the original text chunks, are stored in a specialized vector database.39  
2. **Retrieval (Act Phase):** During its Think phase, the agent determines that it needs a specific piece of information. It then formulates a query and, in its Act phase, calls the RAG tool. This tool takes the agent's query, embeds it using the same model, and performs a semantic similarity search against the vector database to find the most relevant text chunks.39 Advanced RAG systems may use hybrid search (combining semantic and keyword search) and re-rankers to improve the quality of the retrieved results.42  
3. **Augmentation (Observe Phase):** The top-k most relevant text chunks retrieved from the vector database are returned to the agent. This retrieved content is then formatted and inserted into the context window as the Observation for that cycle.40 The agent can now use this new, targeted information in its next  
   Think phase to refine its reasoning or formulate an answer.

#### **Benefits for Context Management**

By treating external knowledge as a queryable resource rather than a static payload, RAG provides profound benefits for context management in agentic systems:

* **Contextual Focus:** RAG keeps the agent's working context (the scratchpad) lean and highly relevant. Instead of being pre-loaded with potentially vast and noisy information, the context is augmented only with the precise snippets of knowledge needed at a specific point in the reasoning process. This directly mitigates the "lost in the middle" problem and reduces the cognitive load on the model.5  
* **Scalability and Currency:** The agent gains access to a virtually unlimited knowledge base without being constrained by its context window size. Furthermore, this knowledge base can be updated continuously and in real-time without the need to retrain or fine-tune the LLM, ensuring the agent's responses are grounded in the most current and accurate information available.4  
* **Reduced Hallucination:** By forcing the agent to base its reasoning on externally retrieved, verifiable facts, RAG significantly reduces the likelihood of factual inaccuracies and hallucinations, a common failure mode for models relying solely on their parametric knowledge.4

### **4.3 Context Engineering: Active Management of the Working Memory**

Context engineering is the "art and science of filling the context window with just the right information for the next step".45 It encompasses a set of software-level strategies for actively managing, pruning, and condensing the agent's scratchpad and conversational history as they grow. These techniques are crucial for long-running agents that must maintain coherence over many turns without overflowing their context limits.

#### **Summarization Techniques**

Summarization strategies aim to compress the conversational history while preserving its essential meaning, trading verbosity for token efficiency.

* **Conversation Summary Buffer:** This is a popular hybrid approach that balances detail with compression. It maintains the most recent N messages or turns of a conversation verbatim in the context window. Once the history grows beyond this window, a separate, often faster and cheaper, LLM call is triggered to summarize the oldest messages. This summary then replaces the original messages in the context.47 This method ensures that the immediate context remains highly detailed for turn-by-turn coherence, while the long-term context is preserved in a compressed form.  
* **Dynamic Summarization ("Auto-Compact"):** A more reactive approach involves monitoring the context window's token count. When it reaches a predefined threshold (e.g., 95% of the maximum limit), a secondary LLM is automatically invoked to summarize the entire history on the fly. This summarized version then becomes the new context for the next turn. This technique, used in systems like Anthropic's Claude Code agent, provides a robust, automated mechanism for preventing context overflow in real-time.46 Automated conversation summaries can also be generated post-conversation for archival and review, providing agents with quick catch-up capabilities for historical interactions.49

#### **Selective Pruning and Compression**

These methods involve more direct manipulation of the context content, either by removing parts of it or by transforming it into a more compact representation.

* **Trimming (Truncation):** The simplest and most computationally efficient strategy is to simply remove the oldest messages from the context history (a First-In, First-Out or FIFO approach) once a token limit is exceeded.48 While fast and easy to implement, this method is naive and carries a significant risk of discarding critical foundational context from the beginning of the interaction, which can cause the agent to lose track of its original goal or user preferences.  
* **Key-Value Memory Extraction:** Instead of storing the full, verbose text of previous turns, a more sophisticated approach involves using an LLM to extract key pieces of information (e.g., user preferences, established facts, important decisions) and storing them in a structured key-value format. This structured data can then be more efficiently injected into the prompt, providing a dense summary of critical information without the token overhead of natural language.  
* **Soft Context Compression:** This is an advanced technique that requires dedicated model training. A separate "compressor" model is trained to take a long sequence of text and condense it into a much shorter sequence of special "summary vectors" or "memory tokens." These compressed representations, which are not human-readable, are then prepended to the prompt for the main LLM. The main LLM is co-trained to understand these compressed representations. This method can achieve very high compression ratios (e.g., up to 16x) while preserving a high degree of fidelity, but its requirement for specialized training makes it less accessible than other approaches.52

The choice among these strategies involves a complex set of trade-offs between performance, cost, and the preservation of reasoning fidelity. The following table provides a practical guide for developers to navigate these choices.  
**Table 2: Context Management Strategies for ReAct Agents**

| Strategy | Operational Description | Ideal Use Case | Key Trade-offs (Latency, Cost, Fidelity) |
| :---- | :---- | :---- | :---- |
| **Retrieval-Augmented Generation (RAG)** | Agent uses a tool to query an external vector database for relevant information on-demand, which is then added to the context as an observation. | Knowledge-intensive tasks requiring access to up-to-date, proprietary, or vast external data sources. | **Latency:** High (adds a network round-trip and database query). **Cost:** Moderate (embedding and query costs). **Fidelity:** High (grounds agent in factual, relevant data). |
| **Conversation History Summarization** | Older parts of the conversation history are periodically replaced with an LLM-generated summary. | Long-running, multi-turn conversational agents where maintaining the gist of the entire interaction is crucial (e.g., customer support, personal assistants). | **Latency:** High (requires an additional LLM call for summarization). **Cost:** High (extra LLM call). **Fidelity:** Medium (summarization can lead to loss of nuance or specific details). |
| **Simple Truncation (FIFO)** | The oldest messages are discarded from the context window once a token limit is reached. | Latency-sensitive applications where recent context is most important and the risk of losing early context is acceptable (e.g., simple Q\&A bots). | **Latency:** Very Low (minimal computation). **Cost:** Very Low (no extra calls). **Fidelity:** Low (high risk of losing critical context, leading to coherence breakdown). |
| **Soft Context Compression** | A pre-trained compressor model condenses long text into a short sequence of summary vectors for the main LLM. | Highly specialized, performance-critical systems where maximum context density is required and the resources for training a custom compressor are available. | **Latency:** Low (at inference). **Cost:** Very High (requires dedicated model training). **Fidelity:** High (designed to preserve information with minimal loss). |

Observing the evolution of these techniques reveals a clear and significant trend: the abstraction of memory management away from the static, underlying model architecture and into a dynamic, agent-controlled software layer. While architectural solutions like Longformer provide a larger, more efficient "hard drive," they do not solve the problem of deciding what information is relevant at any given moment. Agentic workflows are inherently dynamic; the value and relevance of information shift with each step of the reasoning process. Techniques like RAG and agent-driven summarization reframe memory access as an *action*. The agent itself, guided by its reasoning, decides when to retrieve from an external source, when to compress its own history, and what information to prioritize. This represents a fundamental transfer of responsibility from the model's passive architecture to the agent's active cognitive process. This software-defined memory management provides far greater flexibility, adaptability, and intelligence than a purely architectural approach, allowing the agent to function like a sophisticated operating system for its own cognitive resources.

## **Part V: Advanced Memory Systems and Implementation Patterns**

As agentic systems evolve from handling single, isolated tasks to engaging in long-running, multi-session interactions, the need for more sophisticated memory architectures becomes paramount. The ephemeral, in-context scratchpad is insufficient for tasks that require personalization, learning over time, or continuity across conversations. This has led to the development of hybrid memory systems that mirror the distinction between short-term and long-term memory in human cognition, supported by powerful frameworks that formalize agent state management.

### **5.1 Bridging the Gap: Hybrid Short-Term and Long-Term Memory Architectures**

Advanced agents operate with a memory hierarchy, allowing them to efficiently manage information at different timescales and levels of abstraction.

#### **Defining Memory Tiers**

* **Short-Term Memory (Working Memory):** This corresponds directly to the in-context scratchpad discussed previously. It holds the immediate state of the current task—the sequence of thoughts, actions, and observations. It is characterized by high-speed access (as it is part of the prompt) but is volatile, limited in capacity by the context window, and is typically cleared after the task is complete.47  
* **Long-Term Memory:** This is an external, persistent storage system designed to hold information across multiple tasks and sessions. It is typically implemented using a vector database (e.g., Chroma, Redis, Qdrant, Weaviate) that stores memories as semantic embeddings.1 This allows for efficient retrieval of relevant past information based on the context of a new query. Long-term memory is characterized by its large capacity and persistence but has higher latency for access compared to short-term memory.

#### **The Memory Hierarchy in Action**

The two memory tiers work in concert, creating a dynamic flow of information that enables continuous learning and personalization.

* **Writing to Long-Term Memory:** An agent can be equipped with a dedicated tool, often named something like save\_memory or store\_memory. During its reasoning process, the agent can identify key pieces of information from its short-term scratchpad—such as a user's stated preference ("The user prefers concise summaries"), a successfully executed sequence of actions for a common task, or a newly learned fact—and use this tool to commit them to the long-term vector store.54 This process effectively transfers knowledge from volatile working memory to persistent storage.  
* **Reading from Long-Term Memory:** At the beginning of a new task or conversation, a dedicated step can be introduced to query the long-term memory. The current user prompt is used to perform a semantic search against the vector store to retrieve relevant past memories. This retrieved information is then "loaded" into the short-term memory (i.e., prepended to the context window or system prompt), effectively bootstrapping the agent with relevant historical context before it even begins its first Think cycle.53 In graph-based frameworks, this is often implemented as a dedicated  
  load\_memories node that executes at the start of the workflow.55

#### **Types of Long-Term Memory**

Drawing inspiration from cognitive science, developers are beginning to structure long-term memory into different conceptual types to support more nuanced agent behaviors 56:

* **Semantic Memory:** Stores factual knowledge and concepts (e.g., "The user's account number is X," "API key for service Y is Z").  
* **Episodic Memory:** Stores past experiences or sequences of events (e.g., "Last time the user asked for a report, they requested it in CSV format," "The previous attempt to use tool A failed with error B").  
* **Procedural Memory:** Represents learned skills or workflows. While this is often implicitly encoded in the agent's code and prompts, advanced agents might store successful action sequences in memory to recall and reuse for similar future tasks.

### **5.2 Frameworks for State Management: LangGraph and LlamaIndex**

The abstract concepts of memory hierarchies are made concrete and manageable through specialized open-source frameworks that provide the tools to build and persist stateful agentic applications.

#### **LangGraph**

LangGraph is a library for building stateful, multi-agent applications by representing them as graphs. This approach treats agent execution as a formal state management problem, making memory a first-class citizen of the architecture.

* **StateGraph and AgentState:** In LangGraph, an agentic loop is defined as a StateGraph. The memory of the agent is explicitly defined in a typed dictionary called AgentState. This schema can include channels for messages (the short-term memory scratchpad), retrieved documents, user information, or any other piece of state that needs to be tracked.58 The entire agent execution is a series of state transformations, where each node in the graph is a function that takes the current  
  AgentState as input and returns an update to that state.  
* **Checkpointers:** LangGraph's key feature for memory persistence is its checkpointer system. A checkpointer, such as the built-in MemorySaver or integrations with persistent backends like Redis or PostgreSQL, automatically saves the entire AgentState after each step of the graph's execution.53 Each conversation or session is associated with a unique  
  configurable thread\_id. When a new input for an existing thread\_id is received, the checkpointer automatically loads the last saved state, allowing the conversation to resume seamlessly. This provides a robust and elegant solution for managing short-term memory persistence across multiple turns.60

#### **LlamaIndex**

LlamaIndex is a data framework for LLM applications, with a strong focus on connecting LLMs to external data. It provides high-level abstractions for managing agent memory.

* **Memory Modules:** LlamaIndex offers a suite of BaseMemory classes that encapsulate different memory strategies. The ChatMemoryBuffer provides a simple, token-limited buffer for recent conversation history.62 More advanced modules, like  
  VectorMemory or the SimpleComposableMemory, allow for the integration of a vector store as a secondary, long-term memory source. These modules can be composed to create a hybrid memory system where, for instance, older messages from the chat buffer are flushed to the vector memory for long-term storage.64  
* **Integration with Agents:** The chosen memory module is typically passed directly into the agent's .run() or .chat() method. The agent's internal logic then transparently handles the memory lifecycle: putting new messages into the memory module, getting the relevant history from the module before each LLM call, and injecting it into the prompt.62 This high-level API simplifies the process for developers, abstracting away the complexities of prompt management and state persistence. Platforms like Mem0 are also integrating with LlamaIndex to provide specialized, self-improving memory layers that handle compression and personalization automatically.65

The adoption of frameworks like LangGraph signifies a crucial maturation in the design of agentic systems. Early implementations often involved ad-hoc management of state within a single, monolithic loop, typically by passing an ever-growing string or list of messages. This approach is brittle and difficult to scale. By introducing the concept of an explicit, structured AgentState and a formal StateGraph to operate on it, LangGraph reframes agent execution as a robust state management problem. Memory is no longer just an incidental part of the prompt; it is the central, persistent data structure around which the entire workflow is architected. This paradigm shift treats agentic processes not as simple, stateless LLM calls, but as stateful, resilient, and scalable computations, which is essential for building production-ready applications.

### **5.3 Emerging Frontiers: Towards Agentic Memory Organization**

Current research is pushing the boundaries of agent memory beyond simple storage and retrieval, exploring systems where the agent takes on the role of organizing its own knowledge.

* **A-MEM (Agentic Memory):** This novel system proposes a memory architecture where the agent is not just a consumer of memory but also its curator.67 Inspired by the Zettelkasten note-taking method, an agent using A-MEM doesn't just save isolated facts. When a new memory is added, the agent generates a comprehensive, structured "note" with attributes like contextual descriptions and keywords. Crucially, the agent then analyzes its entire existing memory base to identify and create explicit links to other relevant memories, building an interconnected network of knowledge. Furthermore, this process is dynamic; integrating new memories can trigger updates to the representations of existing, linked memories, allowing the knowledge network to evolve and refine itself over time. This approach represents a significant step towards more autonomous cognitive architectures, where agents can manage and structure their own long-term learning process.

## **Conclusion**

The challenge of managing memory in ReAct-based LLM agents is a complex, multi-faceted problem that sits at the intersection of computational complexity, model architecture, and cognitive design. The analysis presented in this report demonstrates that there is no single solution; instead, the development of scalable, efficient, and intelligent agents hinges on the implementation of a coherent, multi-layered memory strategy. The performance bottlenecks stemming from the quadratic complexity of attention and the cognitive limitations of models in long-context scenarios necessitate a holistic approach that addresses constraints at every level of the system.

### **Recapitulation of the Multi-Layered Approach**

An effective memory management strategy synthesizes solutions from three distinct but interconnected layers:

1. **The Architectural Layer:** At the foundation, leveraging models built with efficient attention mechanisms is critical. Technologies like FlashAttention provide significant speedups for exact attention, while approximations like Sparse Attention (found in models such as Longformer) and Linear Attention offer near-linear scaling, making it computationally feasible to handle much larger context windows. The choice of model architecture sets the fundamental performance envelope within which the agent operates.  
2. **The Context Engineering Layer:** Within the agent's operational loop, active management of the context window is essential. Treating Retrieval-Augmented Generation (RAG) as a dynamic tool allows the agent to query vast external knowledge bases on-demand, keeping the immediate context lean and relevant. This must be complemented by context compression techniques, such as conversation summarization, which prune the historical scratchpad to prevent overflow while preserving the gist of the interaction. This layer acts as the agent's "working memory" manager, ensuring the information presented to the LLM is both concise and maximally useful.  
3. **The Memory Systems Layer:** For agents that require personalization and learning over time, a hybrid memory architecture is necessary. This involves integrating the volatile, in-context short-term memory (the scratchpad) with a persistent, external long-term memory, typically a vector database. This hierarchy allows the agent to commit important information to durable storage and recall it in future sessions, enabling true continuity and adaptation. Frameworks like LangGraph and LlamaIndex provide the essential software abstractions to build and manage these stateful systems effectively.

### **Recommendations for Practitioners**

The optimal combination of these strategies depends heavily on the specific requirements of the agentic application. The following recommendations can guide practitioners in designing their memory architecture:

* **For Latency-Sensitive, Real-Time Applications** (e.g., simple customer service bots): Prioritize performance above all. Select models that leverage hardware-optimized attention mechanisms like FlashAttention. For context management, employ simple, computationally inexpensive strategies like fixed-window truncation (FIFO), accepting the risk of context loss in exchange for minimal latency.  
* **For Knowledge-Intensive, Factual Q\&A Agents** (e.g., technical support, research assistants): The primary goal is accuracy and grounding. The core of the memory strategy should be a robust RAG pipeline. Equip the agent with a powerful search tool connected to a comprehensive and up-to-date vector database. The context window should be primarily used to manage the immediate reasoning chain and the retrieved factual snippets.  
* **For Long-Running, Personalized Agents** (e.g., AI tutors, personal assistants, complex workflow orchestrators): These applications require a sophisticated, hybrid memory system. Implement a persistent long-term memory using a vector store. Equip the agent with tools to explicitly save and retrieve memories. Combine this with a conversation summarization strategy (e.g., a summary buffer) to manage the short-term context over extended interactions. Utilize a framework like LangGraph to formally manage the agent's state and persistence.

### **Future Outlook**

The co-evolution of LLM architectures and agentic memory systems will continue to be a driving force in AI research and development. As foundational models become more powerful and context windows expand, the focus will increasingly shift from merely overcoming computational limits to designing more sophisticated cognitive architectures. The future of agentic memory lies in greater autonomy. We can anticipate the principles demonstrated by emerging research like A-MEM becoming more mainstream, leading to agents that do not just use a memory system provided to them but actively and intelligently organize, prune, and evolve their own knowledge structures. This will mark a transition from agents as mere task executors to agents as genuine learning systems, capable of adapting and improving their own cognitive processes through experience. The continued development of these advanced memory architectures will be the key to unlocking the full potential of agentic AI, enabling the creation of systems that are not only powerful but also truly context-aware, personalized, and intelligent.

#### **Works cited**

1. The Landscape of Emerging AI Agent Architectures for Reasoning, Planning, and Tool Calling: A Survey \- arXiv, accessed September 19, 2025, [https://arxiv.org/html/2404.11584v1](https://arxiv.org/html/2404.11584v1)  
2. Agentic Workflows: A Guide to Understanding What They Are, Benefits, and Uses \- Slack, accessed September 19, 2025, [https://slack.com/blog/transformation/agentic-workflows-a-guide-to-understanding-what-they-are-benefits-and-uses](https://slack.com/blog/transformation/agentic-workflows-a-guide-to-understanding-what-they-are-benefits-and-uses)  
3. What Are Agentic Workflows? Patterns, Use Cases, Examples, and More | Weaviate, accessed September 19, 2025, [https://weaviate.io/blog/what-are-agentic-workflows](https://weaviate.io/blog/what-are-agentic-workflows)  
4. What is a ReAct Agent? | IBM, accessed September 19, 2025, [https://www.ibm.com/think/topics/react-agent](https://www.ibm.com/think/topics/react-agent)  
5. The Context Window Problem: Scaling Agents Beyond Token Limits, accessed September 19, 2025, [https://www.factory.ai/context-window-problem](https://www.factory.ai/context-window-problem)  
6. A timeline of LLM Context Windows, Over the past 5 years. (done right this time) \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1mymyfu/a\_timeline\_of\_llm\_context\_windows\_over\_the\_past\_5/](https://www.reddit.com/r/LocalLLaMA/comments/1mymyfu/a_timeline_of_llm_context_windows_over_the_past_5/)  
7. How does having a very long context window impact performance? : r/LocalLLaMA \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1lxuu5m/how\_does\_having\_a\_very\_long\_context\_window\_impact/](https://www.reddit.com/r/LocalLLaMA/comments/1lxuu5m/how_does_having_a_very_long_context_window_impact/)  
8. \[PDF\] ReAct: Synergizing Reasoning and Acting in Language Models \- Semantic Scholar, accessed September 19, 2025, [https://www.semanticscholar.org/paper/ReAct%3A-Synergizing-Reasoning-and-Acting-in-Language-Yao-Zhao/99832586d55f540f603637e458a292406a0ed75d](https://www.semanticscholar.org/paper/ReAct%3A-Synergizing-Reasoning-and-Acting-in-Language-Yao-Zhao/99832586d55f540f603637e458a292406a0ed75d)  
9. ReAct Prompting | Prompt Engineering Guide, accessed September 19, 2025, [https://www.promptingguide.ai/techniques/react](https://www.promptingguide.ai/techniques/react)  
10. ReACT agent LLM: Making GenAI react quickly and decisively \- K2view, accessed September 19, 2025, [https://www.k2view.com/blog/react-agent-llm/](https://www.k2view.com/blog/react-agent-llm/)  
11. Understanding AI Agents through the Thought-Action-Observation Cycle \- Hugging Face, accessed September 19, 2025, [https://huggingface.co/learn/agents-course/unit1/agent-steps-and-structure](https://huggingface.co/learn/agents-course/unit1/agent-steps-and-structure)  
12. Attention Is All You Need \- Wikipedia, accessed September 19, 2025, [https://en.wikipedia.org/wiki/Attention\_Is\_All\_You\_Need](https://en.wikipedia.org/wiki/Attention_Is_All_You_Need)  
13. Mastering the Attention Concept in LLM: Unlocking the Core of Modern AI, accessed September 19, 2025, [https://metadesignsolutions.com/mastering-the-attention-concept-in-llm-unlocking-the-core-of-modern-ai/](https://metadesignsolutions.com/mastering-the-attention-concept-in-llm-unlocking-the-core-of-modern-ai/)  
14. The Mechanism of Attention in Large Language Models: A Comprehensive Guide, accessed September 19, 2025, [https://magnimindacademy.com/blog/the-mechanism-of-attention-in-large-language-models-a-comprehensive-guide/](https://magnimindacademy.com/blog/the-mechanism-of-attention-in-large-language-models-a-comprehensive-guide/)  
15. Attention Mechanism Complexity Analysis | by Mridul Rao \- Medium, accessed September 19, 2025, [https://medium.com/@mridulrao674385/attention-mechanism-complexity-analysis-7314063459b1](https://medium.com/@mridulrao674385/attention-mechanism-complexity-analysis-7314063459b1)  
16. The Problem with Quadratic Attention in Transformer Architectures | tips \- Wandb, accessed September 19, 2025, [https://wandb.ai/wandb\_fc/tips/reports/The-Problem-with-Quadratic-Attention-in-Transformer-Architectures--Vmlldzo3MDE0Mzcz](https://wandb.ai/wandb_fc/tips/reports/The-Problem-with-Quadratic-Attention-in-Transformer-Architectures--Vmlldzo3MDE0Mzcz)  
17. Why does attention need to be fully quadratic? : r/LocalLLaMA \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/150owmj/why\_does\_attention\_need\_to\_be\_fully\_quadratic/](https://www.reddit.com/r/LocalLLaMA/comments/150owmj/why_does_attention_need_to_be_fully_quadratic/)  
18. The End of Transformers? On Challenging Attention and the Rise of Sub-Quadratic Architectures | OpenReview, accessed September 19, 2025, [https://openreview.net/forum?id=N7ouWikDzw](https://openreview.net/forum?id=N7ouWikDzw)  
19. Long-Context Windows in Large Language Models: Applications in Comprehension and Code | by Adnan Masood, PhD. | Medium, accessed September 19, 2025, [https://medium.com/@adnanmasood/long-context-windows-in-large-language-models-applications-in-comprehension-and-code-03bf4027066f](https://medium.com/@adnanmasood/long-context-windows-in-large-language-models-applications-in-comprehension-and-code-03bf4027066f)  
20. What Causes Poor Long-Context Performance? : r/LocalLLaMA \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1lykf92/what\_causes\_poor\_longcontext\_performance/](https://www.reddit.com/r/LocalLLaMA/comments/1lykf92/what_causes_poor_longcontext_performance/)  
21. Why Does the Effective Context Length of LLMs Fall Short? \- arXiv, accessed September 19, 2025, [https://arxiv.org/html/2410.18745v1](https://arxiv.org/html/2410.18745v1)  
22. Breaking the attention bottleneck \- arXiv, accessed September 19, 2025, [https://arxiv.org/html/2406.10906v1](https://arxiv.org/html/2406.10906v1)  
23. Your 1M+ Context Window LLM Is Less Powerful Than You Think | Towards Data Science, accessed September 19, 2025, [https://towardsdatascience.com/your-1m-context-window-llm-is-less-powerful-than-you-think/](https://towardsdatascience.com/your-1m-context-window-llm-is-less-powerful-than-you-think/)  
24. ReAct: Synergizing Reasoning and Acting in Language Models, accessed September 19, 2025, [https://react-lm.github.io/](https://react-lm.github.io/)  
25. Logical Reasoning with ReAct Agent from Scratch in Python: Part 2 ..., accessed September 19, 2025, [https://medium.com/@akash-modi/logical-reasoning-with-react-agent-from-scratch-in-python-part-2-b74ef462244b](https://medium.com/@akash-modi/logical-reasoning-with-react-agent-from-scratch-in-python-part-2-b74ef462244b)  
26. Comprehensive Guide to ReAct Prompting and ReAct based Agentic Systems \- Mercity AI, accessed September 19, 2025, [https://www.mercity.ai/blog-post/react-prompting-and-react-based-agentic-systems](https://www.mercity.ai/blog-post/react-prompting-and-react-based-agentic-systems)  
27. The Scratchpad Talk \- langnostic, accessed September 19, 2025, [https://langnostic.inaimathi.ca/posts/scratchpad-talk-notes](https://langnostic.inaimathi.ca/posts/scratchpad-talk-notes)  
28. Chain of Thought prompting for LLMs \- DataScienceCentral.com, accessed September 19, 2025, [https://www.datasciencecentral.com/chain-of-thought-prompting-for-llms/](https://www.datasciencecentral.com/chain-of-thought-prompting-for-llms/)  
29. A Super Simple ReAct Agent from Scratch | by Sami Maameri | Data Science Collective, accessed September 19, 2025, [https://medium.com/data-science-collective/a-super-simple-react-agent-87913949f69f](https://medium.com/data-science-collective/a-super-simple-react-agent-87913949f69f)  
30. Three AI Design Patterns of Autonomous Agents | by Alexander Sniffin \- Medium, accessed September 19, 2025, [https://alexsniffin.medium.com/three-ai-design-patterns-of-autonomous-agents-8372b9402f7c](https://alexsniffin.medium.com/three-ai-design-patterns-of-autonomous-agents-8372b9402f7c)  
31. "Chain of Thought" is a misnomer. It's not actual thought—it's a scratchpad. True "thoughts" are internal activations. : r/ArtificialInteligence \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/ArtificialInteligence/comments/1mhauta/chain\_of\_thought\_is\_a\_misnomer\_its\_not\_actual/](https://www.reddit.com/r/ArtificialInteligence/comments/1mhauta/chain_of_thought_is_a_misnomer_its_not_actual/)  
32. HYPERATTENTION: LONG-CONTEXT ATTENTION IN NEAR-LINEAR TIME \- OpenReview, accessed September 19, 2025, [https://openreview.net/pdf?id=Eh0Od2BJIM](https://openreview.net/pdf?id=Eh0Od2BJIM)  
33. \[2507.19595\] Efficient Attention Mechanisms for Large Language Models: A Survey \- arXiv, accessed September 19, 2025, [https://arxiv.org/abs/2507.19595](https://arxiv.org/abs/2507.19595)  
34. Beyond Attention: Breaking the Limits of Transformer Context Length with Recurrent Memory, accessed September 19, 2025, [https://ojs.aaai.org/index.php/AAAI/article/view/29722/31239](https://ojs.aaai.org/index.php/AAAI/article/view/29722/31239)  
35. Large language model \- Wikipedia, accessed September 19, 2025, [https://en.wikipedia.org/wiki/Large\_language\_model](https://en.wikipedia.org/wiki/Large_language_model)  
36. Using LangChain ReAct Agents to Answer Complex Questions \- Airbyte, accessed September 19, 2025, [https://airbyte.com/data-engineering-resources/using-langchain-react-agents](https://airbyte.com/data-engineering-resources/using-langchain-react-agents)  
37. ReAct Agent with Query Engine (RAG) Tools \- LlamaIndex Python Documentation, accessed September 19, 2025, [https://docs.llamaindex.ai/en/stable/examples/agent/react\_agent\_with\_query\_engine/](https://docs.llamaindex.ai/en/stable/examples/agent/react_agent_with_query_engine/)  
38. ReAct: Integrating Reasoning and Acting with Retrieval-Augmented Generation (RAG, accessed September 19, 2025, [https://bluetickconsultants.medium.com/react-integrating-reasoning-and-acting-with-retrieval-augmented-generation-rag-a6c2e869f763](https://bluetickconsultants.medium.com/react-integrating-reasoning-and-acting-with-retrieval-augmented-generation-rag-a6c2e869f763)  
39. What is RAG? \- Retrieval-Augmented Generation AI Explained \- AWS \- Updated 2025, accessed September 19, 2025, [https://aws.amazon.com/what-is/retrieval-augmented-generation/](https://aws.amazon.com/what-is/retrieval-augmented-generation/)  
40. Retrieval Augmented Generation (RAG) for LLMs \- Prompt Engineering Guide, accessed September 19, 2025, [https://www.promptingguide.ai/research/rag](https://www.promptingguide.ai/research/rag)  
41. Introducing React Native RAG: Local & Offline Retrieval-Augmented Generation, accessed September 19, 2025, [https://blog.swmansion.com/introducing-react-native-rag-fbb62efa4991](https://blog.swmansion.com/introducing-react-native-rag-fbb62efa4991)  
42. What is Retrieval-Augmented Generation (RAG)? | Google Cloud, accessed September 19, 2025, [https://cloud.google.com/use-cases/retrieval-augmented-generation](https://cloud.google.com/use-cases/retrieval-augmented-generation)  
43. Retrieval-augmented generation \- Wikipedia, accessed September 19, 2025, [https://en.wikipedia.org/wiki/Retrieval-augmented\_generation](https://en.wikipedia.org/wiki/Retrieval-augmented_generation)  
44. What is retrieval-augmented generation (RAG)? \- IBM Research, accessed September 19, 2025, [https://research.ibm.com/blog/retrieval-augmented-generation-RAG](https://research.ibm.com/blog/retrieval-augmented-generation-RAG)  
45. Context Engineering in LLM-Based Agents | by Jin Tan Ruan, CSE Computer Science, accessed September 19, 2025, [https://medium.com/@jtanruan/context-engineering-in-llm-based-agents-d670d6b439bc](https://medium.com/@jtanruan/context-engineering-in-llm-based-agents-d670d6b439bc)  
46. Context engineering is all you need (to build agents), accessed September 19, 2025, [https://www.osedea.com/insight/context-engineering](https://www.osedea.com/insight/context-engineering)  
47. Memory in LLM agents \- DEV Community, accessed September 19, 2025, [https://dev.to/datalynx/memory-in-llm-agents-121](https://dev.to/datalynx/memory-in-llm-agents-121)  
48. How to manage conversation history in a ReAct Agent \- GitHub Pages, accessed September 19, 2025, [https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-manage-message-history/](https://langchain-ai.github.io/langgraph/how-tos/create-react-agent-manage-message-history/)  
49. Overview of Automated Conversation Summaries \- LivePerson Customer Success Center, accessed September 19, 2025, [https://community.liveperson.com/kb/articles/2007-overview-of-automated-conversation-summaries](https://community.liveperson.com/kb/articles/2007-overview-of-automated-conversation-summaries)  
50. Summarize Conversation With AI Summaries \- Gladly Connect, accessed September 19, 2025, [https://help.gladly.com/docs/summarize-conversation-with-ai-summaries](https://help.gladly.com/docs/summarize-conversation-with-ai-summaries)  
51. Managing Context Continuity in Extended AI Agent Interactions : r/AI\_Agents \- Reddit, accessed September 19, 2025, [https://www.reddit.com/r/AI\_Agents/comments/1ibi1sc/managing\_context\_continuity\_in\_extended\_ai\_agent/](https://www.reddit.com/r/AI_Agents/comments/1ibi1sc/managing_context_continuity_in_extended_ai_agent/)  
52. Concise and Precise Context Compression for Tool-Using Language Models \- arXiv, accessed September 19, 2025, [https://arxiv.org/html/2407.02043v1](https://arxiv.org/html/2407.02043v1)  
53. Build smarter AI agents: Manage short-term and long-term memory with Redis | Redis, accessed September 19, 2025, [https://redis.io/blog/build-smarter-ai-agents-manage-short-term-and-long-term-memory-with-redis/](https://redis.io/blog/build-smarter-ai-agents-manage-short-term-and-long-term-memory-with-redis/)  
54. langchain-ai/memory-agent \- GitHub, accessed September 19, 2025, [https://github.com/langchain-ai/memory-agent](https://github.com/langchain-ai/memory-agent)  
55. A Long-Term Memory Agent \- Python LangChain, accessed September 19, 2025, [https://python.langchain.com/docs/versions/migrating\_memory/long\_term\_memory\_agent/](https://python.langchain.com/docs/versions/migrating_memory/long_term_memory_agent/)  
56. Architecting Agent Memory: Principles, Patterns, and Best Practices — Richmond Alake, MongoDB \- YouTube, accessed September 19, 2025, [https://www.youtube.com/watch?v=W2HVdB4Jbjs](https://www.youtube.com/watch?v=W2HVdB4Jbjs)  
57. LangGraph Memory Management \- Overview, accessed September 19, 2025, [https://langchain-ai.github.io/langgraph/concepts/memory/](https://langchain-ai.github.io/langgraph/concepts/memory/)  
58. How to create a ReAct agent from scratch \- GitHub Pages, accessed September 19, 2025, [https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/](https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/)  
59. LangGraph Multi-Agent Systems \- Overview, accessed September 19, 2025, [https://langchain-ai.github.io/langgraph/concepts/multi\_agent/](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)  
60. Building AI Agents Using LangGraph: Part 5 \- Adding Memory to the Agent \- HARSHA J S, accessed September 19, 2025, [https://harshaselvi.medium.com/building-ai-agents-using-langgraph-part-5-adding-memory-to-the-agent-d2ef16e68e67](https://harshaselvi.medium.com/building-ai-agents-using-langgraph-part-5-adding-memory-to-the-agent-d2ef16e68e67)  
61. Building a ReAct Agent with LLM, Tools, and Memory Saver: A Step-by-Step Guide | by mohit basantani | Medium, accessed September 19, 2025, [https://medium.com/@mohitbasantani1987/building-a-react-agent-with-llm-tools-and-memory-saver-a-step-by-step-guide-1b1fee88e210](https://medium.com/@mohitbasantani1987/building-a-react-agent-with-llm-tools-and-memory-saver-a-step-by-step-guide-1b1fee88e210)  
62. Memory \- LlamaIndex, accessed September 19, 2025, [https://docs.llamaindex.ai/en/stable/module\_guides/deploying/agents/memory/](https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/)  
63. Chat Memory Buffer \- LlamaIndex Python Documentation, accessed September 19, 2025, [https://docs.llamaindex.ai/en/stable/examples/agent/memory/chat\_memory\_buffer/](https://docs.llamaindex.ai/en/stable/examples/agent/memory/chat_memory_buffer/)  
64. Simple Composable Memory \- LlamaIndex Python Documentation, accessed September 19, 2025, [https://docs.llamaindex.ai/en/stable/examples/agent/memory/composable\_memory/](https://docs.llamaindex.ai/en/stable/examples/agent/memory/composable_memory/)  
65. LlamaIndex ReAct Agent \- Mem0 Documentation, accessed September 19, 2025, [https://docs.mem0.ai/examples/llama-index-mem0](https://docs.mem0.ai/examples/llama-index-mem0)  
66. Mem0 \- The Memory Layer for your AI Apps, accessed September 19, 2025, [https://mem0.ai/](https://mem0.ai/)  
67. \[2502.12110\] A-MEM: Agentic Memory for LLM Agents \- arXiv, accessed September 19, 2025, [https://arxiv.org/abs/2502.12110](https://arxiv.org/abs/2502.12110)  
68. Conversational Memory for LLMs with Langchain \- Pinecone, accessed September 22, 2025, [https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/](https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/)  
69. GenAI — Managing Context History Best Practices | by VerticalServe Blogs \- Medium, accessed September 22, 2025, [https://verticalserve.medium.com/genai-managing-context-history-best-practices-a350e57cc25f](https://verticalserve.medium.com/genai-managing-context-history-best-practices-a350e57cc25f)  
70. Agent & Tools — ReAct Chat \- by Shravan Kumar \- Medium, accessed September 22, 2025, [https://medium.com/@shravankoninti/agent-tools-react-chat-43ffc67d4cf4](https://medium.com/@shravankoninti/agent-tools-react-chat-43ffc67d4cf4)  
71. \[Part IV\] LlamaIndex ReAct Agent Workflows — Are we thinking enough? \- Medium, accessed September 22, 2025, [https://medium.com/mitb-for-all/part-iv-llamaindex-react-workflows-are-we-thinking-enough-232cd44a6677](https://medium.com/mitb-for-all/part-iv-llamaindex-react-workflows-are-we-thinking-enough-232cd44a6677)  
72. langchain.agents.react.agent.create\_react\_agent, accessed September 22, 2025, [https://api.python.langchain.com/en/latest/agents/langchain.agents.react.agent.create\_react\_agent.html](https://api.python.langchain.com/en/latest/agents/langchain.agents.react.agent.create_react_agent.html)  
73. The Significance of Conversation History and Memory in Prompt Engineering: Shaping the Future of AI-Powered Conversations | by Mark Craddock \- Medium, accessed September 22, 2025, [https://medium.com/prompt-engineering/the-significance-of-conversation-history-and-memory-in-prompt-engineering-shaping-the-future-of-be9d10a3d027](https://medium.com/prompt-engineering/the-significance-of-conversation-history-and-memory-in-prompt-engineering-shaping-the-future-of-be9d10a3d027)  
74. Difference between Memory and {agent\_scratchpad}? : r/LangChain \- Reddit, accessed September 22, 2025, [https://www.reddit.com/r/LangChain/comments/17on184/difference\_between\_memory\_and\_agent\_scratchpad/](https://www.reddit.com/r/LangChain/comments/17on184/difference_between_memory_and_agent_scratchpad/)  
75. You're doing Agentic chat history wrong | OpenAI Agents SDK \- YouTube, accessed September 22, 2025, [https://www.youtube.com/watch?v=9nwWJWyxSyk](https://www.youtube.com/watch?v=9nwWJWyxSyk)  
76. How do you currently manage conversation history and user context in your LLM-api apps, and what challenges or costs do you face as your interactions grow longer or more complex? : r/AI\_Agents \- Reddit, accessed September 22, 2025, [https://www.reddit.com/r/AI\_Agents/comments/1ld1ey0/how\_do\_you\_currently\_manage\_conversation\_history/](https://www.reddit.com/r/AI_Agents/comments/1ld1ey0/how_do_you_currently_manage_conversation_history/)