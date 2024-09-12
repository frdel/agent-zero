import os
import asyncio
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv
import yaml
import aiohttp
import json
import time
import base64
import nltk
from PIL import Image
import io
import language_tool_python
import dspy
from nltk.sentiment import SentimentIntensityAnalyzer
import traceback
from openai import AsyncOpenAI
from python.helpers.tool import Tool, Response
from python.helpers import files
import csv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info(f"Wordware API Key loaded: {'*' * (len(os.getenv('WORDWARE_API_KEY')) - 4) + os.getenv('WORDWARE_API_KEY')[-4:]}")

# Initialize NLTK and LanguageTool
nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
sia = SentimentIntensityAnalyzer()
grammar_tool = language_tool_python.LanguageTool('en-US')

# Initialize DSPy (GPT-4 model)
turbo = dspy.OpenAI(model="gpt-4")
dspy.settings.configure(lm=turbo)

# Initialize AsyncOpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PipelineManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.pipelines = self.load_pipelines()

    def load_pipelines(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)['pipelines']

    def save_pipelines(self):
        with open(self.config_path, 'w') as file:
            yaml.dump({'pipelines': self.pipelines}, file)

    def add_pipeline(self, name: str, config: Dict[str, Any]):
        self.pipelines[name] = config
        self.save_pipelines()

    def update_pipeline(self, name: str, config: Dict[str, Any]):
        if name in self.pipelines:
            self.pipelines[name].update(config)
            self.save_pipelines()

    def remove_pipeline(self, name: str):
        if name in self.pipelines:
            del self.pipelines[name]
            self.save_pipelines()

    def get_pipeline(self, name: str) -> Dict[str, Any]:
        return self.pipelines.get(name, {})

# DSPy Signature for Content Generation Task
class GenerateContent(dspy.Signature):
    topic = dspy.InputField()
    content_type = dspy.InputField()
    guidelines = dspy.InputField()
    content = dspy.OutputField()

# DSPy Signature for Tone Refinement Task
class RefineTone(dspy.Signature):
    content = dspy.InputField()
    tone = dspy.InputField()
    refined_content = dspy.OutputField()

# DSPy Signature for Quality Check Task
class QualityCheck(dspy.Signature):
    content = dspy.InputField()
    corrected_content = dspy.OutputField()

# Content Generation Module using DSPy Chain of Thought
class ContentGeneratorModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_content = dspy.ChainOfThought(GenerateContent)

    def forward(self, topic, content_type, guidelines):
        content = self.generate_content(topic=topic, content_type=content_type, guidelines=guidelines).content
        return content

# Tone Refinement Module using DSPy Chain of Thought
class ToneRefinementModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.refine_tone = dspy.ChainOfThought(RefineTone)

    def forward(self, content, tone):
        refined_content = self.refine_tone(content=content, tone=tone).refined_content
        return refined_content

# Quality Check Module using LanguageTool for grammar checking
class QualityCheckModule(dspy.Module):
    def forward(self, content):
        matches = grammar_tool.check(content)
        corrected_content = language_tool_python.utils.correct(content, matches)
        return corrected_content

# Image Generation and Evaluation Logic using DSPy
class ImageGenerationModule(dspy.Module):
    def __init__(self, api_url, api_key):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate_image(self, topic: str, pipeline_name: str, max_attempts: int = 5) -> List[str]:
        logger.info(f"Starting image generation for {pipeline_name} about {topic}")
        prompt = f"Create an image for a {pipeline_name} about {topic}"
        url = self.api_url
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "inputs": {"Prompt": prompt},
            "version": "^1.0"
        }
        
        async def attempt_generation():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status != 200:
                            logger.error(f"Error: API response status {response.status}")
                            response_text = await response.text()
                            logger.error(f"Response content: {response_text}")
                            return None

                        full_response = await response.text()
                        logger.info(f"Full API response: {full_response}")

                        # Process the response as a stream of JSON objects
                        for line in full_response.split('\n'):
                            if line.strip():
                                try:
                                    chunk = json.loads(line)
                                    if chunk['type'] == 'chunk' and 'value' in chunk:
                                        value = chunk['value']
                                        if 'type' in value and value['type'] == 'outputs':
                                            outputs = value.get('values', {})
                                            for output in outputs.values():
                                                if 'output' in output and 'image_url' in output['output']:
                                                    return output['output']['image_url']
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse JSON line: {line}")

                        logger.error("Image URL not found in the response")
                        return None
            except Exception as e:
                logger.error(f"Error in attempt_generation: {str(e)}")
                logger.error(traceback.format_exc())
                return None

        generated_images = []
        for attempt in range(max_attempts):
            logger.info(f"Attempt {attempt + 1} of {max_attempts}")
            try:
                image_url = await attempt_generation()
                if image_url:
                    logger.info("Image URL received, evaluating...")
                    try:
                        score, evaluation = await self.evaluate_image(image_url, pipeline_name, topic)
                        logger.info(f"Image evaluation (Attempt {attempt + 1}):\nScore: {score}\n{evaluation}")
                        
                        if score >= 6:  # Consider the image good enough if score is 6 or higher
                            generated_images.append(image_url)
                            logger.info(f"Image URL added: {image_url}")
                            break
                        else:
                            logger.info(f"Image score too low ({score}/10). Attempting again...")
                    except Exception as e:
                        logger.error(f"Error evaluating image: {str(e)}")
                        logger.error(traceback.format_exc())
                else:
                    logger.warning(f"Attempt {attempt + 1} failed: No image URL received")
            except Exception as e:
                logger.error(f"Error in attempt {attempt + 1}: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not generated_images:
            logger.warning(f"Failed to generate a satisfactory image after {max_attempts} attempts.")
        
        logger.info(f"Image generation complete. Generated {len(generated_images)} images.")
        return generated_images

    async def evaluate_image(self, image_url, pipeline_name, topic):
        evaluation_prompt = f"""
        Evaluate this image for {pipeline_name} about {topic}. 
        Consider relevance, visual appeal, professionalism, and suitability for {pipeline_name}. 
        Your response should start with 'Score: X/10' on its own line.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": evaluation_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ]
        )
        evaluation = response.choices[0].message.content.strip()

        try:
            score_line = next(line for line in evaluation.split('\n') if line.startswith('Score:'))
            score = float(score_line.split(':')[1].split('/')[0].strip())
        except (StopIteration, ValueError):
            logger.warning("Failed to extract score, assuming 0.")
            score = 0

        return score, evaluation

# Main Pipeline that orchestrates the content generation, refinement, and quality check
class ContentPipeline(dspy.Module):
    def __init__(self, image_api_url, image_api_key):
        super().__init__()
        self.content_generator = ContentGeneratorModule()
        self.tone_refiner = ToneRefinementModule()
        self.quality_checker = QualityCheckModule()
        self.image_generator = ImageGenerationModule(image_api_url, image_api_key)

    async def forward(self, topic, content_type, guidelines, tone, pipeline_name):
        # Step 1: Generate content
        content = self.content_generator(topic=topic, content_type=content_type, guidelines=guidelines)
        # Step 2: Refine the tone
        refined_content = self.tone_refiner(content=content, tone=tone)
        # Step 3: Check quality
        final_content = self.quality_checker(content=refined_content)
        # Step 4: Generate images
        generated_images = await self.image_generator.generate_image(topic, pipeline_name)

        return {
            "content": final_content,
            "images": generated_images
        }

class ContentGenerationApp:
    def __init__(self, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.content_pipeline = ContentPipeline(
            image_api_url="https://app.wordware.ai/api/released-app/8e77b0d4-0a0a-4169-ac35-0ce33a5bd028/run",
            image_api_key=os.getenv('WORDWARE_API_KEY')
        )

    async def generate_content(self, pipeline_name: str, topic: str) -> Dict[str, Any]:
        pipeline = self.pipeline_manager.get_pipeline(pipeline_name)
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_name} not found in config")

        content_type = pipeline.get('content_type', 'LinkedIn post')
        guidelines = pipeline.get('guidelines', 'Create engaging and relevant content.')
        tone = pipeline.get('tone', 'professional')

        result = await self.content_pipeline(
            topic=topic,
            content_type=content_type,
            guidelines=guidelines,
            tone=tone,
            pipeline_name=pipeline_name
        )
        return result

class LinkedInContentGenerator(Tool):
    def __init__(self, agent, name, args, message):
        super().__init__(agent, name, args, message)
        config_path = files.get_abs_path("python/tools/content_config.yml")
        self.pipeline_manager = PipelineManager(config_path)
        self.app = ContentGenerationApp(self.pipeline_manager)

    async def execute(self, action="generate", pipeline_name="", topic="", **kwargs) -> Response:
        if action == "generate":
            if not pipeline_name or not topic:
                return Response(message="Please provide both 'pipeline_name' and 'topic'.", break_loop=False)
            try:
                result = await self.app.generate_content(pipeline_name, topic)
                response_message = f"Generated content for '{topic}' using '{pipeline_name}' pipeline:\n\n"
                response_message += f"Content:\n{result['content']}\n\n"
                if result['images']:
                    response_message += f"Generated Images: {', '.join(result['images'])}"
                else:
                    response_message += "No images were generated."
                return Response(message=response_message, break_loop=False)
            except Exception as e:
                error_message = f"Error generating content: {str(e)}"
                self.agent.context.log.log(type="error", content=error_message)
                return Response(message=error_message, break_loop=False)
        elif action == "bulk_generate":
            if not pipeline_name or not kwargs.get("topics"):
                return Response(message="Please provide 'pipeline_name' and 'topics' for bulk generation.", break_loop=False)
            try:
                topics = kwargs["topics"]
                results = []
                for topic in topics:
                    result = await self.app.generate_content(pipeline_name, topic)
                    results.append({
                        "topic": topic,
                        "content": result["content"],
                        "images": result["images"]
                    })
                csv_content = self.generate_csv(results)
                return Response(message=f"Bulk generation completed. CSV content:\n\n{csv_content}", break_loop=False)
            except Exception as e:
                return Response(message=f"Error in bulk generation: {str(e)}", break_loop=False)
        elif action == "add_pipeline":
            name = kwargs.get("name")
            config = kwargs.get("config")
            if name and config:
                self.pipeline_manager.add_pipeline(name, config)
                return Response(message=f"Pipeline '{name}' added successfully.", break_loop=False)
            else:
                return Response(message="Invalid arguments for adding a pipeline.", break_loop=False)
        elif action == "update_pipeline":
            name = kwargs.get("name")
            config = kwargs.get("config")
            if name and config:
                self.pipeline_manager.update_pipeline(name, config)
                return Response(message=f"Pipeline '{name}' updated successfully.", break_loop=False)
            else:
                return Response(message="Invalid arguments for updating a pipeline.", break_loop=False)
        elif action == "remove_pipeline":
            name = kwargs.get("name")
            if name:
                self.pipeline_manager.remove_pipeline(name)
                return Response(message=f"Pipeline '{name}' removed successfully.", break_loop=False)
            else:
                return Response(message="Invalid arguments for removing a pipeline.", break_loop=False)
        elif action == "list_tools":
            tools = [
                "generate",
                "bulk_generate",
                "add_pipeline",
                "update_pipeline",
                "remove_pipeline",
                "list_tools"
            ]
            tools_description = "\n".join([f"- {tool}" for tool in tools])
            return Response(message=f"Available tools:\n{tools_description}", break_loop=False)
        else:
            return Response(message="Invalid action. Supported actions are 'generate', 'bulk_generate', 'add_pipeline', 'update_pipeline', 'remove_pipeline', and 'list_tools'.", break_loop=False)

    def generate_csv(self, results):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Tweet Content", "Image1", "Image2", "Image3", "Image4"])
        for result in results:
            row = [result["content"]] + result["images"][:4] + [''] * (4 - len(result["images"]))
            writer.writerow(row)
        return output.getvalue()

# Main entry point to run the DSPy-based content generation
async def main():
    config_path = files.get_abs_path("python/tools/content_config.yml")
    pipeline_manager = PipelineManager(config_path)
    generator = ContentGenerationApp(pipeline_manager)
    results = await generator.generate_all_content()

    for result in results:
        print(f"Generated Content: {result['content']}")
        print(f"Generated Images: {result['images']}")

if __name__ == "__main__":
    asyncio.run(main())
