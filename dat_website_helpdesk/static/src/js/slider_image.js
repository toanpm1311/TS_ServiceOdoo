let currentImages = [];
let currentImageIndex = 0;

function openSlider(imageUrls, startIndex = 0) {
    currentImages = imageUrls;
    currentImageIndex = startIndex;

    document.getElementById('imageSlider').style.display = 'block';
    document.body.style.overflow = 'hidden';

    updateImage();
    createThumbnails();
    scrollToActiveThumbnail();
}

function closeSlider() {
    document.getElementById('imageSlider').style.display = 'none';
    document.body.style.overflow = 'auto';
}

function updateImage() {
    document.getElementById('mainImage').src = currentImages[currentImageIndex];
    document.getElementById('currentIndex').textContent = currentImageIndex + 1;
    document.getElementById('totalCount').textContent = currentImages.length;
    updateActiveThumbnail();
}

function createThumbnails() {
    const wrapper = document.getElementById('thumbnailsWrapper');
    wrapper.innerHTML = '';

    currentImages.forEach((src, index) => {
        const thumbnail = document.createElement('div');
        thumbnail.className = 'thumbnail';
        if (index === currentImageIndex) thumbnail.classList.add('active');

        const img = document.createElement('img');
        img.src = src;
        img.alt = `Thumbnail ${index + 1}`;

        thumbnail.appendChild(img);
        thumbnail.onclick = () => selectImage(index);
        wrapper.appendChild(thumbnail);
    });
}

function updateActiveThumbnail() {
    document.querySelectorAll('.thumbnail').forEach((thumb, index) => {
        thumb.classList.toggle('active', index === currentImageIndex);
    });
}

function selectImage(index) {
    currentImageIndex = index;
    updateImage();
    scrollToActiveThumbnail();
}

function previousImage() {
    currentImageIndex = (currentImageIndex - 1 + currentImages.length) % currentImages.length;
    updateImage();
    scrollToActiveThumbnail();
}

function nextImage() {
    currentImageIndex = (currentImageIndex + 1) % currentImages.length;
    updateImage();
    scrollToActiveThumbnail();
}

function scrollToActiveThumbnail() {
    const activeThumb = document.querySelector('.thumbnail.active');
    if (activeThumb) {
        activeThumb.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest',
            inline: 'center'
        });
    }
}

// Keyboard và event handlers khác...