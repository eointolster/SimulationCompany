# SoftwareSim3d/src/llm_integration/api_clients.py

import os
import asyncio
import logging
from dotenv import load_dotenv

# Import specific clients - assuming standard installations
import google.generativeai as genai
from openai import AsyncOpenAI, OpenAIError
from anthropic import AsyncAnthropic, AnthropicError

# --- Basic Logging Setup ---
# Configure logging for better traceability of API calls and errors
# Use the existing logger from the calling module or configure one here
# Assuming a logger is passed or configured globally. If not, uncomment below:
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__) # Use the standard Python logger
# --- ---

class LLMService:
    """
    Handles interaction with Google Gemini, OpenAI, and Anthropic models.
    Loads API keys from .env file and provides a unified interface.
    Includes enhanced logging for debugging.
    """
    def __init__(self):
        """
        Loads API keys and configures clients upon instantiation.
        """
        logger.info("Initializing LLMService...")
        load_dotenv() # Load variables from .env file into environment

        # --- Get API Keys ---
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # --- Configure Clients ---
        self.google_client = self._configure_google_client()
        self.openai_client = self._configure_openai_client()
        self.anthropic_client = self._configure_anthropic_client()

        if not any([self.google_client, self.openai_client, self.anthropic_client]):
            logger.error("LLMService initialized, but NO API clients could be configured. Check API keys.")
        else:
            logger.info("LLMService initialized successfully.")

    def _configure_google_client(self):
        """Configures and returns the Google GenAI client."""
        if not self.google_api_key:
            logger.warning("GOOGLE_API_KEY not found in .env file. Google Gemini API will be unavailable.")
            return None
        try:
            genai.configure(api_key=self.google_api_key)
            logger.info("Google GenAI client configured.")
            return genai # Return the configured module itself
        except Exception as e:
            logger.error(f"Failed to configure Google GenAI client: {e}")
            return None

    def _configure_openai_client(self):
        """Configures and returns the OpenAI client."""
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not found in .env file. OpenAI API will be unavailable.")
            return None
        try:
            client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI client configured.")
            return client
        except OpenAIError as e:
            logger.error(f"Failed to configure OpenAI client: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI client configuration: {e}")
            return None

    def _configure_anthropic_client(self):
        """Configures and returns the Anthropic client."""
        if not self.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not found in .env file. Anthropic API will be unavailable.")
            return None
        try:
            client = AsyncAnthropic(api_key=self.anthropic_api_key)
            logger.info("Anthropic client configured.")
            return client
        except AnthropicError as e:
            logger.error(f"Failed to configure Anthropic client: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during Anthropic client configuration: {e}")
            return None

    # --- START DEBUG --- Enhanced generate method with more detailed logging
    async def generate(self, llm_type: str, prompt: str, model_name: str = None, max_retries: int = 3, initial_delay: int = 1) -> str:
        """
        Enhanced generate method with more detailed logging for debugging.
        """
        # --- Start Debug Logging ---
        logger.info(f"LLM DEBUG: generate called with '{llm_type}' (model: {model_name or 'default'})")
        logger.info(f"LLM DEBUG: prompt length: {len(prompt)}")
        logger.info(f"LLM DEBUG: prompt preview: {prompt[:100]}...")
        # --- End Debug Logging ---

        attempt = 0
        delay = initial_delay

        # Before entering the retry loop, verify the client exists
        client_exists = False
        client_available_msg = "available"
        if llm_type == 'gemini':
            if self.google_client: client_exists = True
            else: client_available_msg = "not configured or API key missing"
        elif llm_type == 'openai':
            if self.openai_client: client_exists = True
            else: client_available_msg = "not configured or API key missing"
        elif llm_type == 'anthropic':
            if self.anthropic_client: client_exists = True
            else: client_available_msg = "not configured or API key missing"
        else:
             client_available_msg = f"type '{llm_type}' is not supported"

        # --- Start Debug Logging ---
        if client_exists:
             logger.info(f"LLM DEBUG: Client for '{llm_type}' is available.")
        else:
             error_msg = f"LLM DEBUG: Client for '{llm_type}' is {client_available_msg}."
             logger.error(error_msg)
             return f"Error: {error_msg}" # Return error early if client invalid/missing
        # --- End Debug Logging ---

        while attempt < max_retries:
            try:
                # --- Start Debug Logging ---
                logger.info(f"LLM DEBUG: Starting attempt {attempt+1}/{max_retries} for {llm_type}")
                # --- End Debug Logging ---

                if llm_type == 'gemini':
                    model_to_use = model_name if model_name else "gemini-2.5-pro-preview-03-25"
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: Calling gemini: {model_to_use}")
                    # --- End Debug Logging ---
                    result = await self._call_gemini(prompt, model_to_use)
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: gemini call completed (attempt {attempt+1}), result length: {len(result)}")
                    # --- End Debug Logging ---
                    return result # Return on first success

                elif llm_type == 'openai':
                    model_to_use = model_name if model_name else "gpt-4o"
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: Calling openai: {model_to_use}")
                    # --- End Debug Logging ---
                    result = await self._call_openai(prompt, model_to_use)
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: openai call completed (attempt {attempt+1}), result length: {len(result)}")
                    # --- End Debug Logging ---
                    return result # Return on first success

                elif llm_type == 'anthropic':
                    model_to_use = model_name if model_name else "claude-3-7-sonnet-20240229"
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: Calling anthropic: {model_to_use}")
                    # --- End Debug Logging ---
                    result = await self._call_anthropic(prompt, model_to_use)
                    # --- Start Debug Logging ---
                    logger.info(f"LLM DEBUG: anthropic call completed (attempt {attempt+1}), result length: {len(result)}")
                    # --- End Debug Logging ---
                    return result # Return on first success

                else: # Should have been caught earlier, but defensively handle
                    error_msg = f"LLM type '{llm_type}' is not supported."
                    logger.error(f"LLM DEBUG: {error_msg}")
                    return f"Error: {error_msg}"

            except (OpenAIError, AnthropicError, Exception) as e:
                error_details = str(e)
                 # --- Start Debug Logging ---
                logger.error(f"LLM DEBUG: Exception during attempt {attempt+1}: {error_details}", exc_info=True)
                # --- End Debug Logging ---

                # Check if the error is likely transient
                # Refine this based on specific API error codes if possible
                is_transient = isinstance(e, (OpenAIError, AnthropicError)) or "rate_limit" in error_details.lower() or "server error" in error_details.lower()
                # --- Start Debug Logging ---
                logger.info(f"LLM DEBUG: Error classified as transient: {is_transient}")
                # --- End Debug Logging ---

                if is_transient and attempt < max_retries - 1:
                    attempt += 1
                    # --- Start Debug Logging ---
                    logger.warning(f"LLM DEBUG: Retrying (Attempt {attempt+1}/{max_retries}). Delay: {delay}s")
                    # --- End Debug Logging ---
                    await asyncio.sleep(delay)
                    delay *= 2 # Exponential backoff
                else: # Non-transient error or max retries reached
                    error_msg = f"LLM call failed after {attempt+1} attempts for {llm_type}: {error_details}"
                    # --- Start Debug Logging ---
                    logger.error(f"LLM DEBUG: {error_msg}")
                    # --- End Debug Logging ---
                    return f"Error: {error_msg}" # Return the error message

        # Fallback if loop finishes without returning (shouldn't happen with current logic)
        final_error_msg = f"LLM generation failed for {llm_type} after exhausting retries (unexpected loop exit)."
        # --- Start Debug Logging ---
        logger.error(f"LLM DEBUG: {final_error_msg}")
        # --- End Debug Logging ---
        return f"Error: {final_error_msg}"
    # --- END DEBUG ---


    # --- START DEBUG --- Add detailed logging to the provider-specific methods
    async def _call_gemini(self, prompt: str, model_name: str) -> str:
        """Internal method to call the Google Gemini API with enhanced logging."""
        try:
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: _call_gemini - Using model: {model_name}")
             # --- End Debug Logging ---
             model = self.google_client.GenerativeModel(model_name)
             # --- Start Debug Logging ---
             logger.info("LLM DEBUG: Google model instance created")
             # --- End Debug Logging ---

             loop = asyncio.get_running_loop()
             # --- Start Debug Logging ---
             logger.info("LLM DEBUG: About to call Google API via executor")
             # --- End Debug Logging ---
             response = await loop.run_in_executor(None, model.generate_content, prompt)
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: Google API call completed")
             # --- End Debug Logging ---

             # Check for response status and content blocking
             if not response.parts:
                 if response.prompt_feedback and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     # --- Start Debug Logging ---
                     logger.warning(f"LLM DEBUG: Gemini response blocked due to: {block_reason}")
                     # --- End Debug Logging ---
                     return f"Error: Content blocked by API ({block_reason})"
                 else:
                     # --- Start Debug Logging ---
                     logger.warning("LLM DEBUG: Gemini response was empty or missing parts.")
                     # --- End Debug Logging ---
                     return "Error: Empty response from API"

             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: Successful Gemini response, text length: {len(response.text)}")
             # --- End Debug Logging ---
             return response.text
        except Exception as e:
             # --- Start Debug Logging ---
             logger.error(f"LLM DEBUG: Error during Gemini API call ({model_name}): {e}", exc_info=True)
             # --- End Debug Logging ---
             raise # Re-raise for the main generate method's retry logic

    async def _call_openai(self, prompt: str, model_name: str) -> str:
        """Internal method to call the OpenAI API with enhanced logging."""
        try:
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: _call_openai - Using model: {model_name}")
             logger.info("LLM DEBUG: About to call OpenAI API chat.completions.create")
             # --- End Debug Logging ---

             response = await self.openai_client.chat.completions.create(
                 model=model_name,
                 messages=[{"role": "user", "content": prompt}]
             )
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: OpenAI API call completed")
             # --- End Debug Logging ---

             content = response.choices[0].message.content.strip()
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: Successful OpenAI response, content length: {len(content)}")
             # --- End Debug Logging ---
             return content
        except Exception as e: # Catch OpenAIError specifically if needed for different handling
            # --- Start Debug Logging ---
            logger.error(f"LLM DEBUG: Error during OpenAI API call ({model_name}): {e}", exc_info=True)
            # --- End Debug Logging ---
            raise # Re-raise for retry logic

    async def _call_anthropic(self, prompt: str, model_name: str) -> str:
        """Internal method to call the Anthropic API with enhanced logging."""
        try:
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: _call_anthropic - Using model: {model_name}")
             logger.info("LLM DEBUG: About to call Anthropic API messages.create")
             # --- End Debug Logging ---

             response = await self.anthropic_client.messages.create(
                 model=model_name,
                 max_tokens=8192, # Consider making this configurable
                 messages=[
                     {
                         "role": "user",
                         "content": prompt
                     }
                 ]
             )
             # --- Start Debug Logging ---
             logger.info(f"LLM DEBUG: Anthropic API call completed")
             # --- End Debug Logging ---

             if response.content and isinstance(response.content, list):
                 content = "".join([block.text for block in response.content if hasattr(block, 'text')])
                 # --- Start Debug Logging ---
                 logger.info(f"LLM DEBUG: Successful Anthropic response (list), content length: {len(content)}")
                 # --- End Debug Logging ---
                 return content
             # Add checks for older response structures if necessary
             else:
                 # --- Start Debug Logging ---
                 logger.warning(f"LLM DEBUG: Unexpected Anthropic response structure: {response}")
                 # --- End Debug Logging ---
                 return "Error: Could not parse Anthropic response."
        except Exception as e: # Catch AnthropicError specifically if needed
            # --- Start Debug Logging ---
            logger.error(f"LLM DEBUG: Error during Anthropic API call ({model_name}): {e}", exc_info=True)
            # --- End Debug Logging ---
            raise # Re-raise for retry logic
    # --- END DEBUG ---