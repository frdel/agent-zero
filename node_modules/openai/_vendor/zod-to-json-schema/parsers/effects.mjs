import { parseDef } from "../parseDef.mjs";
export function parseEffectsDef(_def, refs) {
    return refs.effectStrategy === 'input' ? parseDef(_def.schema._def, refs) : {};
}
//# sourceMappingURL=effects.mjs.map