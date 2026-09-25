/* Default first-time visits to Brazilian Portuguese without overriding a
 * language already selected by the user or restored by Psono after login. */
(function () {
  try {
    if (!window.localStorage.getItem("i18nextLng")) {
      window.localStorage.setItem("i18nextLng", "pt-BR");
    }
  } catch (_error) {
    /* Storage can be unavailable in hardened browsers; Psono will fall back
     * to its normal browser-language detection in that case. */
  }
})();
