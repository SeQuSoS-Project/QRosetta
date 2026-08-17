// Tailwind build config. The stylesheet it produces (css/tailwind.css) is committed, so
// the pages need no build step and no CDN at runtime — see scripts/build_css.sh.
module.exports = {
  content: ["./*.html", "./js/**/*.js"],
  theme: { extend: {} },
  plugins: [],
};
