export default function (context) {
  context.processStepTypes.add("wait");
  // Historical wait steps were logged as "progress"; this plugin owns their presentation.
  context.processStepTypes.add("progress");
}
