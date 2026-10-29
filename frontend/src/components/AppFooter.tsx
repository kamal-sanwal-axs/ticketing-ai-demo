export function AppFooter() {
  return (
    <footer className="footer muted">
      <a href="https://api.apex-dev.axsdevops.io/search/swagger/index.html" target="_blank" rel="noopener">
        Search API docs
      </a>
      {" · "}
      <a href="https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json" target="_blank" rel="noopener">
        search openapi
      </a>
      {" · "}
      <a href="https://apex-dev.axsdevops.io/login" target="_blank" rel="noopener">
        apex-dev login
      </a>
    </footer>
  );
}
