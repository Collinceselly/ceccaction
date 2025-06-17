window.onscroll = function() {
    const navbar = document.getElementById("mainNavbar");
    if (window.scrollY > 50) { // Change after scrolling 50px
        navbar.classList.add("scrolled");
    } else {
        navbar.classList.remove("scrolled");
    }
};