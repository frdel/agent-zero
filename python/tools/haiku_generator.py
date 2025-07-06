"""
Haiku Generator Tool for Agent Zero
Demonstrates tool-based generative UI pattern like the LangGraph example
"""

import json
import random
from typing import Dict, Any, List

from python.helpers.tool import Tool, Response


class HaikuGenerator(Tool):
    """
    A tool for generating haiku with accompanying images, demonstrating
    the tool-based generative UI pattern from LangGraph examples.
    """

    def __init__(self, agent, name: str, method: str | None, args: dict[str, str], message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Available images (similar to the LangGraph example)
        self.image_list = [
            "Osaka_Castle_Turret_Stone_Wall_Pine_Trees_Daytime.jpg",
            "Tokyo_Skyline_Night_Tokyo_Tower_Mount_Fuji_View.jpg", 
            "Itsukushima_Shrine_Miyajima_Floating_Torii_Gate_Sunset_Long_Exposure.jpg",
            "Takachiho_Gorge_Waterfall_River_Lush_Greenery_Japan.jpg",
            "Bonsai_Tree_Potted_Japanese_Art_Green_Foliage.jpeg",
            "Shirakawa-go_Gassho-zukuri_Thatched_Roof_Village_Aerial_View.jpg",
            "Ginkaku-ji_Silver_Pavilion_Kyoto_Japanese_Garden_Pond_Reflection.jpg",
            "Senso-ji_Temple_Asakusa_Cherry_Blossoms_Kimono_Umbrella.jpg",
            "Cherry_Blossoms_Sakura_Night_View_City_Lights_Japan.jpg",
            "Mount_Fuji_Lake_Reflection_Cherry_Blossoms_Sakura_Spring.jpg"
        ]

    async def execute(self, **kwargs) -> Response:
        """Execute the haiku generator tool"""
        try:
            action = self.args.get("action", "generate")
            theme = self.args.get("theme", "nature")
            
            if action == "generate":
                return await self._generate_haiku(theme)
            elif action == "list_images":
                return await self._list_available_images()
            elif action == "custom":
                return await self._create_custom_haiku()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available actions: generate, list_images, custom",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Haiku generator failed: {str(e)}",
                break_loop=False
            )

    async def _generate_haiku(self, theme: str) -> Response:
        """Generate a haiku with selected images"""
        
        # Generate haiku based on theme
        haiku_data = self._create_haiku_content(theme)
        
        # Select relevant images
        selected_images = self._select_relevant_images(theme, haiku_data["japanese"])
        
        # Create AG-UI component to display haiku with images
        haiku_display = {
            "type": "container",
            "properties": {
                "layout": "vertical",
                "class": "haiku-showcase"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"# Haiku: {theme.title()}",
                        "variant": "heading"
                    }
                },
                {
                    "type": "container",
                    "properties": {
                        "layout": "horizontal",
                        "class": "haiku-content"
                    },
                    "children": [
                        {
                            "type": "card",
                            "properties": {
                                "title": "Japanese (日本語)",
                                "content": self._format_haiku_lines(haiku_data["japanese"])
                            }
                        },
                        {
                            "type": "card", 
                            "properties": {
                                "title": "English Translation",
                                "content": self._format_haiku_lines(haiku_data["english"])
                            }
                        }
                    ]
                },
                {
                    "type": "container",
                    "properties": {
                        "layout": "horizontal",
                        "class": "image-gallery"
                    },
                    "children": [
                        {
                            "type": "text",
                            "properties": {
                                "content": f"**Selected Images:** {', '.join(selected_images)}",
                                "variant": "caption"
                            }
                        }
                    ]
                },
                {
                    "type": "container",
                    "properties": {
                        "layout": "horizontal", 
                        "class": "haiku-actions"
                    },
                    "children": [
                        {
                            "type": "button",
                            "properties": {
                                "label": "Generate New Haiku",
                                "variant": "primary"
                            },
                            "events": {
                                "click": f"window.generateHaiku('{theme}')"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "Change Theme",
                                "variant": "secondary"
                            },
                            "events": {
                                "click": "window.showThemeSelector()"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "Save Haiku",
                                "variant": "secondary"
                            },
                            "events": {
                                "click": f"window.saveHaiku({json.dumps(haiku_data)})"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Generated Haiku",
            content=json.dumps({
                "ui_components": haiku_display,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0",
                "haiku_data": haiku_data,
                "selected_images": selected_images
            })
        )
        
        return Response(
            message=f"🌸 Generated haiku on theme '{theme}' with {len(selected_images)} selected images!\n\nThe interactive haiku display has been created above with Japanese text, English translation, and curated imagery.",
            break_loop=False
        )

    async def _list_available_images(self) -> Response:
        """List all available images"""
        
        image_gallery = {
            "type": "container",
            "properties": {
                "layout": "vertical"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": "## Available Images for Haiku",
                        "variant": "heading"
                    }
                },
                {
                    "type": "list",
                    "properties": {
                        "items": [{"content": img} for img in self.image_list],
                        "variant": "bulleted"
                    }
                },
                {
                    "type": "text",
                    "properties": {
                        "content": f"**Total Images:** {len(self.image_list)}",
                        "variant": "caption"
                    }
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Available Images",
            content=json.dumps({
                "ui_components": image_gallery,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message=f"📷 Listed {len(self.image_list)} available images for haiku generation.",
            break_loop=False
        )

    async def _create_custom_haiku(self) -> Response:
        """Create a custom haiku input form"""
        
        custom_form = {
            "type": "container",
            "properties": {
                "layout": "vertical"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": "## Create Custom Haiku",
                        "variant": "heading"
                    }
                },
                {
                    "type": "form",
                    "id": "custom-haiku-form",
                    "properties": {
                        "action": "/ag_ui_form_submit",
                        "method": "POST"
                    },
                    "events": {
                        "submit": "window.submitCustomHaiku(event)"
                    },
                    "children": [
                        {
                            "type": "text",
                            "properties": {
                                "content": "**Japanese Lines:**",
                                "variant": "label"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "Line 1 (5 syllables)",
                                "name": "japanese_line1"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "Line 2 (7 syllables)",
                                "name": "japanese_line2"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "Line 3 (5 syllables)",
                                "name": "japanese_line3"
                            }
                        },
                        {
                            "type": "text",
                            "properties": {
                                "content": "**English Translation:**",
                                "variant": "label"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "English line 1",
                                "name": "english_line1"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "English line 2",
                                "name": "english_line2"
                            }
                        },
                        {
                            "type": "input",
                            "properties": {
                                "type": "text",
                                "placeholder": "English line 3",
                                "name": "english_line3"
                            }
                        },
                        {
                            "type": "dropdown",
                            "properties": {
                                "placeholder": "Select theme",
                                "name": "theme",
                                "options": [
                                    {"value": "nature", "label": "Nature"},
                                    {"value": "seasons", "label": "Seasons"},
                                    {"value": "water", "label": "Water"},
                                    {"value": "mountains", "label": "Mountains"},
                                    {"value": "temples", "label": "Temples"},
                                    {"value": "cherry_blossoms", "label": "Cherry Blossoms"}
                                ]
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "Create Haiku",
                                "variant": "primary",
                                "type": "submit"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Custom Haiku Creator",
            content=json.dumps({
                "ui_components": custom_form,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message="📝 Custom haiku creation form has been generated! Fill in the Japanese lines, English translation, and select a theme to create your personalized haiku.",
            break_loop=False
        )

    def _create_haiku_content(self, theme: str) -> Dict[str, List[str]]:
        """Create haiku content based on theme"""
        
        # Predefined haiku templates by theme
        haiku_templates = {
            "nature": {
                "japanese": [
                    "古池や",
                    "蛙飛び込む",
                    "水の音"
                ],
                "english": [
                    "An ancient pond",
                    "A frog leaps in",
                    "The sound of water"
                ]
            },
            "seasons": {
                "japanese": [
                    "春の夜の",
                    "桜咲く道",
                    "月明り"
                ],
                "english": [
                    "Spring evening path",
                    "Cherry blossoms bloom",
                    "In moonlight's glow"
                ]
            },
            "water": {
                "japanese": [
                    "川の音",
                    "石の間流れ",
                    "静寂なり"
                ],
                "english": [
                    "River's gentle sound",
                    "Flowing between the stones",
                    "Peaceful silence"
                ]
            },
            "mountains": {
                "japanese": [
                    "富士山よ",
                    "雲の上に立つ",
                    "永遠に"
                ],
                "english": [
                    "Mount Fuji stands",
                    "Above the shifting clouds",
                    "For eternity"
                ]
            }
        }
        
        return haiku_templates.get(theme, haiku_templates["nature"])

    def _select_relevant_images(self, theme: str, japanese_lines: List[str]) -> List[str]:
        """Select 3 relevant images based on theme and content"""
        
        # Theme-based image mapping
        theme_mapping = {
            "nature": ["Bonsai_Tree", "Takachiho_Gorge", "Cherry_Blossoms"],
            "seasons": ["Cherry_Blossoms", "Mount_Fuji", "Senso-ji_Temple"],
            "water": ["Takachiho_Gorge", "Itsukushima_Shrine", "Mount_Fuji_Lake"],
            "mountains": ["Mount_Fuji", "Shirakawa-go", "Tokyo_Skyline"],
            "temples": ["Senso-ji_Temple", "Ginkaku-ji", "Itsukushima_Shrine"]
        }
        
        # Get theme-relevant images
        relevant_keywords = theme_mapping.get(theme, ["Cherry_Blossoms", "Mount_Fuji", "Bonsai_Tree"])
        
        selected_images = []
        for keyword in relevant_keywords:
            matching_images = [img for img in self.image_list if keyword in img]
            if matching_images:
                selected_images.append(matching_images[0])
        
        # If we don't have 3 images, fill with random ones
        while len(selected_images) < 3:
            remaining_images = [img for img in self.image_list if img not in selected_images]
            if remaining_images:
                selected_images.append(random.choice(remaining_images))
            else:
                break
                
        return selected_images[:3]

    def _format_haiku_lines(self, lines: List[str]) -> str:
        """Format haiku lines for display"""
        return "\n".join(f"*{line}*" for line in lines)