# python/extensions/monologue_start/include_attachments.py
from python.helpers.extension import Extension
from python.helpers.attachment_manager import AttachmentManager
from agent import Agent, LoopData
import os

class IncludeAttachments(Extension):
  async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
      attachments = self.agent.get_data('attachments') or []
      if attachments:
          loop_data.attachments = []
          file_manager = AttachmentManager(os.path.join(os.getcwd(), 'work_dir'))
          
          for attachment in attachments:
              if os.path.exists(attachment):
                  filename = os.path.basename(attachment)
                  file_type = file_manager.get_file_type(filename)
                  
                  attachment_html = f'<div class="attachment-item attachment-{file_type}">'
                  if file_type == 'image':
                    preview = file_manager.generate_image_preview(attachment)
                    if preview:
                        attachment_html += f'<img src="data:image/jpeg;base64,{preview}" alt="{filename}" class="attachment-preview"/>'
                  else:
                    # Add placeholder for non-image files
                    attachment_html += f'<div class="attachment-placeholder">{file_type.upper()}</div>'
                  
                  # Add filename and extension badge
                  ext = file_manager.get_file_extension(filename)
                  attachment_html += f'''
                    <div class="attachment-info">
                        <span class="attachment-name">{filename}</span>
                        <span class="attachment-badge">{ext}</span>
                    </div>
                  </div>'''
                  
                  loop_data.attachments.append(attachment_html)
          
          # Clear attachments after processing
          self.agent.set_data('attachments', [])