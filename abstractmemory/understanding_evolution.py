"""
Understanding Evolution Detector for AbstractMemory.

Detects when unresolved questions are answered by new information and
automatically transfers resolved understanding to appropriate memory layers.

This creates the "I just understood that..." self-awareness capability.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# AbstractCore imports
from abstractllm.processing.basic_judge import BasicJudge
from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)


class UnderstandingEvolutionDetector:
    """
    Detects when unresolved questions are answered by new information.
    
    This component enables automatic understanding evolution by:
    1. Checking new information against unresolved questions
    2. Using AbstractCore's BasicJudge to assess if questions are resolved
    3. Automatically transferring resolved understanding to memory
    4. Generating AI self-awareness notes ("I just understood that...")
    """

    def __init__(self, memory_session, llm_provider):
        """
        Initialize the Understanding Evolution Detector.

        Args:
            memory_session: MemorySession instance for memory operations
            llm_provider: LLM provider for judgment operations
        """
        self.memory_session = memory_session
        self.llm_provider = llm_provider
        self.logger = get_logger(__name__)
        
        # Initialize AbstractCore's BasicJudge for assessment
        try:
            self.judge = BasicJudge(llm=llm_provider)
            self.logger.info("UnderstandingEvolutionDetector initialized with AbstractCore BasicJudge")
        except Exception as e:
            self.logger.error("Failed to initialize BasicJudge", error=str(e))
            self.judge = None

    def check_question_resolution(self, 
                                 new_information: str, 
                                 conversation_context: str,
                                 user_id: str = "user") -> List[Dict[str, Any]]:
        """
        Check if new information resolves any unresolved questions.

        Args:
            new_information: New information from conversation
            conversation_context: Full conversation context
            user_id: User ID for context

        Returns:
            List[Dict]: List of resolved questions with metadata
        """
        if not self.judge:
            self.logger.warning("BasicJudge not available, skipping question resolution check")
            return []

        try:
            # Get current unresolved questions
            unresolved_questions = self.memory_session.working_memory.get_unresolved()
            
            if not unresolved_questions:
                self.logger.debug("No unresolved questions to check")
                return []

            self.logger.info(f"Checking {len(unresolved_questions)} unresolved questions against new information")
            
            resolutions = []
            for question_data in unresolved_questions:
                question = question_data.get('question', '')
                if not question:
                    continue
                    
                # Use AbstractCore's BasicJudge to assess if question is resolved
                resolution = self._assess_question_resolution(
                    question=question,
                    new_information=new_information,
                    conversation_context=conversation_context,
                    question_context=question_data.get('context', '')
                )
                
                if resolution:
                    resolution['original_question_data'] = question_data
                    resolution['user_id'] = user_id
                    resolutions.append(resolution)

            self.logger.info(f"Found {len(resolutions)} resolved questions")
            return resolutions

        except Exception as e:
            self.logger.error(f"Error checking question resolution: {e}")
            return []

    def _assess_question_resolution(self, 
                                   question: str, 
                                   new_information: str,
                                   conversation_context: str,
                                   question_context: str) -> Optional[Dict[str, Any]]:
        """
        Use BasicJudge to assess if a question is resolved by new information.

        Args:
            question: The unresolved question
            new_information: New information from conversation
            conversation_context: Full conversation context
            question_context: Context when question was created

        Returns:
            Dict with resolution data if resolved, None otherwise
        """
        try:
            # Create assessment prompt for BasicJudge
            assessment_text = f"""
Question: {question}

Original Context: {question_context}

New Information: {new_information}

Full Conversation Context: {conversation_context[:1000]}...
"""

            # Use BasicJudge to evaluate if question is resolved
            assessment = self.judge.evaluate(
                text=assessment_text,
                criteria=[
                    "question_answered",    # Is the question directly answered?
                    "confidence",          # How confident is the answer?
                    "completeness",        # Is the answer complete?
                    "relevance"           # Is the answer relevant to the question?
                ],
                context="question_resolution_assessment"
            )

            # Extract assessment results
            question_answered = assessment.get('question_answered', False)
            confidence = float(assessment.get('confidence', 0.0))
            completeness = float(assessment.get('completeness', 0.0))
            relevance = float(assessment.get('relevance', 0.0))

            # Determine if question is resolved based on thresholds
            is_resolved = (
                question_answered and 
                confidence >= 0.7 and 
                completeness >= 0.6 and 
                relevance >= 0.7
            )

            if is_resolved:
                # Extract the answer from the new information
                answer = self._extract_answer(question, new_information, conversation_context)
                
                return {
                    'question': question,
                    'answer': answer,
                    'confidence': confidence,
                    'completeness': completeness,
                    'relevance': relevance,
                    'resolution_method': 'conversation_based',
                    'timestamp': datetime.now(),
                    'provenance': {
                        'source': 'conversation',
                        'context': conversation_context[:500],
                        'assessment_scores': {
                            'confidence': confidence,
                            'completeness': completeness,
                            'relevance': relevance
                        }
                    }
                }

            return None

        except Exception as e:
            self.logger.error(f"Error assessing question resolution: {e}")
            return None

    def _extract_answer(self, question: str, new_information: str, context: str) -> str:
        """
        Extract the specific answer to the question from new information.

        Args:
            question: The resolved question
            new_information: New information containing the answer
            context: Full conversation context

        Returns:
            str: Extracted answer
        """
        try:
            # Use LLM to extract the specific answer
            extraction_prompt = f"""
Extract the specific answer to this question from the provided information:

Question: {question}

Information: {new_information}

Context: {context[:500]}...

Please provide a concise, direct answer to the question based on the information provided.
"""

            response = self.llm_provider.generate(extraction_prompt)
            answer = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            return answer

        except Exception as e:
            self.logger.error(f"Error extracting answer: {e}")
            return new_information[:200] + "..." if len(new_information) > 200 else new_information

    def process_resolutions(self, resolutions: List[Dict[str, Any]]) -> bool:
        """
        Process resolved questions and update memory layers.

        Args:
            resolutions: List of resolved questions with metadata

        Returns:
            bool: True if processing successful
        """
        if not resolutions:
            return True

        try:
            self.logger.info(f"Processing {len(resolutions)} resolved questions")

            for resolution in resolutions:
                # 1. Move from unresolved to resolved in working memory
                self._move_to_resolved(resolution)
                
                # 2. Create semantic memory entry
                self._create_semantic_memory(resolution)
                
                # 3. Generate AI self-awareness note
                self._generate_understanding_note(resolution)

            self.logger.info(f"Successfully processed {len(resolutions)} resolutions")
            return True

        except Exception as e:
            self.logger.error(f"Error processing resolutions: {e}")
            return False

    def _move_to_resolved(self, resolution: Dict[str, Any]):
        """Move question from unresolved to resolved in working memory."""
        try:
            self.memory_session.working_memory.add_resolved(
                question=resolution['question'],
                solution=resolution['answer'],
                method=resolution['resolution_method']
            )
            
            # Remove from unresolved (this would need to be implemented in WorkingMemoryManager)
            # For now, we'll leave it in unresolved and rely on periodic cleanup
            
        except Exception as e:
            self.logger.error(f"Error moving to resolved: {e}")

    def _create_semantic_memory(self, resolution: Dict[str, Any]):
        """Create semantic memory entry for resolved understanding."""
        try:
            # Use the memory session's remember_fact tool
            fact_content = f"Understanding: {resolution['question']} → {resolution['answer']}"
            
            self.memory_session.remember_fact(
                content=fact_content,
                importance=0.8,
                emotion="understanding",
                reason=f"Resolved through conversation (confidence: {resolution['confidence']:.2f})"
            )
            
        except Exception as e:
            self.logger.error(f"Error creating semantic memory: {e}")

    def _generate_understanding_note(self, resolution: Dict[str, Any]):
        """Generate 'I just understood that...' note for AI self-awareness."""
        try:
            timestamp = resolution['timestamp']
            confidence = resolution['confidence']
            
            note_content = f"""I just understood that {resolution['question']}

The answer is: {resolution['answer']}

This understanding emerged from our conversation on {timestamp.strftime('%Y-%m-%d %H:%M:%S')}. 
I feel a sense of clarity about this topic now (confidence: {confidence:.2f}).

This resolves a question I've been carrying, and I can now build upon this understanding in future interactions.

Provenance: {resolution['provenance']['source']} - {resolution['resolution_method']}
"""
            
            # Store as experiential note using the memory session's internal method
            self.memory_session._store_experiential_note(
                note_content=note_content,
                user_id=resolution.get('user_id', 'system'),
                location="internal_reflection",
                verbatim_id=f"understanding_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                emotional_resonance={
                    'importance': 0.8,
                    'alignment_with_values': 0.9,
                    'reason': 'Understanding evolution enhances my ability to help'
                },
                unresolved_questions=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error generating understanding note: {e}")

    def get_recent_understanding_evolution(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent understanding evolution events.

        Args:
            days: Number of days to look back

        Returns:
            List[Dict]: Recent understanding evolution events
        """
        try:
            # This would query the memory system for recent understanding notes
            # For now, return empty list as this requires integration with storage
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting recent understanding evolution: {e}")
            return []


def create_understanding_detector(memory_session, llm_provider) -> UnderstandingEvolutionDetector:
    """
    Create an UnderstandingEvolutionDetector instance.

    Args:
        memory_session: MemorySession instance
        llm_provider: LLM provider for judgment operations

    Returns:
        UnderstandingEvolutionDetector instance
    """
    return UnderstandingEvolutionDetector(memory_session=memory_session, llm_provider=llm_provider)
