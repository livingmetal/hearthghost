const candidate = process.argv[2];

if (!new Set(["vrm", "pixi"]).has(candidate)) {
  throw new Error("candidate must be vrm or pixi");
}

await import(`./dist/${candidate}/${candidate}-candidate.js`);
console.log(`${candidate} candidate imported`);
