import uuid
from mimetypes import guess_type

from langchain_core.messages import HumanMessage

from helpers import (
    chat_media,
    ephemeral_images,
    files,
    history,
    images,
    parallel_tools,
    runtime,
)
from helpers.tool import Response, Tool
from helpers.strings import truncate_text
from plugins._model_config.helpers.model_config import (
    build_vision_model,
    get_chat_model_config,
    get_vision_model_config,
)

# image token estimation for context window
TOKENS_ESTIMATE = 1500


class VisionLoad(Tool):
    def get_log_object(self):
        return self.agent.context.log.log(
            type="vision_load",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        paths = self.args.get("paths") or []
        if isinstance(paths, str):
            paths = [paths]
        names = [files.basename(str(path)) for path in paths if str(path).strip()]
        if not names:
            return "icon://imagesmode Loading images"
        text = f"Loading images: {truncate_text(names[0], 60)}"
        if len(names) > 1:
            text += f" + {len(names) - 1} more"
        return f"icon://imagesmode {text}"

    async def execute(
        self,
        paths: list[str] | str = [],
        query: str = "",
        **kwargs,
    ) -> Response:

        self.images_dict = {}
        self.loaded_paths: list[str] = []
        self.skipped_paths: list[str] = []
        self.vision_config = get_vision_model_config(self.agent)
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list):
            return Response(
                message="vision_load error: `paths` must be a string or an array.",
                break_loop=False,
            )

        max_embeds = self._get_max_embeds()
        requested = [
            (str(path or "").strip(), self._display_input_path(str(path or "").strip(), idx + 1))
            for idx, path in enumerate(paths)
        ]
        limited_paths = requested if max_embeds <= 0 else requested[-max_embeds:]
        self.skipped_paths = (
            [display for _, display in requested[:-max_embeds]]
            if max_embeds > 0 and len(requested) > max_embeds
            else []
        )

        for idx, (path, display_path) in enumerate(limited_paths):
            if not path:
                continue
            if ephemeral_images.is_ref(path):
                image = ephemeral_images.consume_image(
                    path,
                    context_id=self._context_id(),
                )
                if image is None:
                    continue
                display = image.display_name or display_path
                stored_ref = self._store_ephemeral_image(image)
                if stored_ref:
                    self.images_dict[display] = stored_ref
                    self.loaded_paths.append(display)
                continue
            if self._is_data_image_url(path):
                stored_ref = self._store_data_url(path, preferred_name=f"vision-load-{idx + 1}.png")
                if stored_ref:
                    self.images_dict[display_path] = stored_ref
                    self.loaded_paths.append(display_path)
                continue
            if not await runtime.call_development_function(files.exists, str(path)):
                continue

            if path not in self.images_dict:
                mime_type, _ = guess_type(str(path))
                if mime_type and mime_type.startswith("image/"):
                    try:
                        stored_ref = self._store_local_image(path, preferred_name=files.basename(path))
                        self.images_dict[display_path] = stored_ref
                        self.loaded_paths.append(display_path)
                    except (FileNotFoundError, OSError, ValueError):
                        continue

        message = self._summary() if self.images_dict or self.skipped_paths else "No images processed"
        if self.vision_config and self.images_dict:
            try:
                capsule = await self._call_vision_model(
                    list(self.images_dict.values()),
                    query,
                )
                message = (
                    f"Analyzed {len(self.images_dict)} image(s)"
                    f"; {len(self.skipped_paths)} skipped.\n\n{capsule.strip()}"
                )
            except Exception as exc:
                message = f"Image analysis error: {str(exc)[:1000]}"
        return Response(message=message, break_loop=False)

    def _get_max_embeds(self) -> int:
        cfg = self.vision_config or get_chat_model_config(self.agent)
        return int(cfg.get("max_embeds", 10) or 0)

    def _context_id(self) -> str:
        context = getattr(self.agent, "context", None)
        get_data = getattr(context, "get_data", None)
        parent_id = (
            get_data(parallel_tools.PARALLEL_WORKER_PARENT_CONTEXT_KEY)
            if get_data
            else ""
        )
        return str(parent_id or getattr(context, "id", "") or "").strip()

    async def _call_vision_model(self, image_paths: list[str], query: str) -> str:
        user_message = getattr(self.agent, "last_user_message", None)
        output_text = getattr(user_message, "output_text", None)
        request = str(output_text() if callable(output_text) else "").strip()
        content = [
            {
                "type": "text",
                "text": self.agent.read_prompt(
                    "fw.vision_load.md",
                    request=request,
                    query=str(query or "").strip(),
                ),
            }
        ]
        content.extend(
            {"type": "image_url", "image_url": {"url": path}}
            for path in image_paths
        )
        response, _ = await build_vision_model(self.agent).unified_call(
            messages=[HumanMessage(content=content)],
        )
        if not str(response or "").strip():
            raise RuntimeError("Vision Model returned an empty response.")
        return str(response)

    def _store_ephemeral_image(self, image: ephemeral_images.EphemeralImage) -> str:
        context_id = self._context_id()
        if not context_id:
            return image.data_url
        source = chat_media.infer_source(image.ref, image.display_name)
        category = chat_media.category_for_source(source)
        saved = chat_media.save_image_base64(
            context_id=context_id,
            data=image.data,
            mime_type=image.mime,
            category=category,
            source=source,
            preferred_name=image.display_name,
        )
        return saved.a0_path

    def _store_data_url(self, data_url: str, *, preferred_name: str = "") -> str:
        context_id = self._context_id()
        if not context_id:
            return data_url
        source = chat_media.infer_source(data_url, preferred_name)
        category = chat_media.category_for_source(source)
        saved = chat_media.save_image_data_url(
            context_id=context_id,
            data_url=data_url,
            category=category,
            source=source,
            preferred_name=preferred_name,
        )
        return saved.a0_path

    def _store_local_image(self, path: str, *, preferred_name: str = "") -> str:
        context_id = self._context_id()
        if not context_id:
            return images.to_data_url(path)
        return chat_media.materialize_image_ref(
            context_id=context_id,
            url=path,
            source=chat_media.infer_source(path, preferred_name),
            preferred_name=preferred_name,
        )

    def _summary(self) -> str:
        loaded = "\n".join(self.loaded_paths) if self.loaded_paths else "none"
        summary = f"Loaded images ({len(self.loaded_paths)}):\n{loaded}"
        if self.skipped_paths:
            summary += (
                f"\n\nSkipped images ({len(self.skipped_paths)}, max {self._get_max_embeds()}):\n"
                + "\n".join(self.skipped_paths)
            )
        return summary

    @staticmethod
    def _is_data_image_url(value: str) -> bool:
        normalized = str(value or "").strip().lower()
        return normalized.startswith("data:image/") and ";base64," in normalized

    @classmethod
    def _display_input_path(cls, value: str, index: int) -> str:
        if ephemeral_images.is_ref(value):
            return ephemeral_images.display_ref(value)
        if cls._is_data_image_url(value):
            prefix = value.split(",", 1)[0]
            return f"{prefix},<ephemeral-image-{index}>"
        return value

    async def after_execution(self, response: Response, **kwargs):
        await super().after_execution(response, **kwargs)
        if self.images_dict and not self.vision_config:
            content = [
                {"type": "image_url", "image_url": {"url": image_path}}
                for image_path in self.images_dict.values()
            ]
            raw_message = history.RawMessage(
                raw_content=content,
                preview="<Image attachments loaded by path>",
            )
            tokens = TOKENS_ESTIMATE * len(content)
            if not parallel_tools.queue_parallel_parent_history(
                self.agent,
                content=raw_message,
                tokens=tokens,
            ):
                self.agent.hist_add_message(
                    False,
                    content=raw_message,
                    tokens=tokens,
                )
