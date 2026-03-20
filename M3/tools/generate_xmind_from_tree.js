'use strict';

const fs = require('fs');
const path = require('path');

async function main() {
  const modulePath = process.argv[2];
  const outputPath = process.argv[3];
  const inputPath = process.argv[4];

  if (!modulePath || !outputPath) {
    throw new Error('Usage: node generate_xmind_from_tree.js <xmind-module-path> <output-path.xmind> [tree-json-path]');
  }

  const source = (inputPath ? fs.readFileSync(inputPath, 'utf8') : fs.readFileSync(0, 'utf8')).trim();
  if (!source) {
    throw new Error(inputPath ? `Missing tree JSON in file: ${inputPath}` : 'Missing tree JSON on stdin');
  }

  const tree = JSON.parse(source);
  const { Workbook, Topic, Zipper } = require(modulePath);

  const workbook = new Workbook();
  const rootTitle = tree.title || 'Mind Map';
  const sheet = workbook.createSheet(rootTitle, rootTitle);
  const topic = new Topic({ sheet });
  const rootId = topic.cid();
  let sequence = 0;

  function addNodes(nodes, parentId) {
    for (const node of nodes || []) {
      const customId = `topic_${++sequence}`;
      topic.on(parentId).add({
        title: String(node.title || '').trim() || 'Untitled',
        customId,
      });
      addNodes(node.children, topic.cid());
    }
  }

  addNodes(tree.children, rootId);

  const target = path.resolve(outputPath);
  const zipper = new Zipper({
    path: path.dirname(target),
    workbook,
    filename: path.basename(target, '.xmind'),
  });

  const status = await zipper.save();
  if (!status) {
    throw new Error('Zipper.save() returned false');
  }

  process.stdout.write(`${zipper.target()}\n`);
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});