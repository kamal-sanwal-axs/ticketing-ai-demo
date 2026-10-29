/** Default stub — overwritten by user files at runtime. */
export default function App({ input }) {
  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <h2>Sandbox React</h2>
      <pre>{JSON.stringify(input, null, 2)}</pre>
    </div>
  );
}
