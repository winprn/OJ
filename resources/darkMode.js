const setTheme = (theme) => {
  const sun = document.querySelector(".sun");
  const moon = document.querySelector(".moon");
  const body = document.querySelector("body");

  if (theme === "dark") {
    sun.classList.add("hidden");
    moon.classList.remove("hidden");
    body.classList.add("dark");
    localStorage.setItem("theme", "dark");
  } else {
    moon.classList.add("hidden");
    sun.classList.remove("hidden");
    body.classList.remove("dark");
    localStorage.setItem("theme", "light");
  }
};

window.onload = () => {
  const currentTheme = localStorage.getItem("theme");
  console.log(currentTheme);
  if (currentTheme === null) currentTheme = "light";

  setTheme(currentTheme);
};

const toggleButton = document.querySelector(".toggle");
toggleButton.addEventListener("click", () => {
  const body = document.querySelector("body");

  if (body.classList.contains("dark")) setTheme("light");
  else setTheme("dark");
});
