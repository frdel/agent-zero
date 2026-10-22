import { drawMessageToolSimple } from "/js/messages.js";

export default async function registerDocumentQueryHandler(extData) {
  if (extData?.type === "document_query") {
    extData.handler = (log) =>
      drawMessageToolSimple({ ...log, code: "DOC" });
  }
}
