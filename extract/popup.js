document.addEventListener('DOMContentLoaded', function () {
  const el = document.getElementById('ver')
  try {
    el.textContent = 'نسخهٔ ' + chrome.runtime.getManifest().version
  } catch (err) {
    el.textContent = ''
  }
})
