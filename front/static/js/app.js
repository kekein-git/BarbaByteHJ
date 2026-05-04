document.addEventListener("DOMContentLoaded", () => {
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach((flash) => {
        setTimeout(() => {
            flash.style.opacity = "0";
            flash.style.transform = "translateY(-4px)";
        }, 3600);
    });
});
