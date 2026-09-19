/**
 * Custom handler for wait tool messages
 * The wait plugin owns the legacy progress presentation: current `wait` logs
 * and historical `progress` records render with the corrected HLD badge.
 */
import {
  buildDetailPayload,
  cleanStepTitle,
  drawProcessStep,
} from "/js/messages.js";
import { store as stepDetailStore } from "/components/modals/process-step-detail/step-detail-store.js";
import { createActionButton } from "/components/messages/action-buttons/simple-action-buttons.js";

export default function (extData) {
  if (extData.type !== "wait" && extData.type !== "progress") return;

  extData.handler = function (log) {
    return drawProcessStep({
      id: log.id,
      title: cleanStepTitle(log.heading || log.content),
      code: "HLD",
      classes: undefined,
      kvps: log.kvps,
      content: log.content,
      actionButtons: [
        createActionButton("detail", "", () =>
          stepDetailStore.showStepDetail(
            buildDetailPayload(log, { headerLabels: [] })
          )
        ),
      ],
      log,
    });
  };
}
