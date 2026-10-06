// No UI or server; initialize the installed editor engine and parse its blank fixture.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root = path.resolve(process.argv[2]);
const dir = path.join(root, 'editor/studio-dist/node');
const m = await import(pathToFileURL(path.join(dir, 'rhwp.js')).href);
m.initSync({module: fs.readFileSync(path.join(dir, 'rhwp_bg.wasm'))});
const doc = new m.HwpDocument(fs.readFileSync(path.join(root, 'editor/blank.hwpx')));
const count = doc.getParagraphCount(0);
if (!(count > 0)) throw new Error('Editor could not read its blank document');
doc.free();
console.log(JSON.stringify({status:'PASS', wasm_initialized:true, paragraphs:count}));
