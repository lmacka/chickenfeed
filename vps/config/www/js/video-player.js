/**
 * Video player module for handling video streaming
 */

/**
 * Initializes the HLS video player
 * @param {HTMLElement} videoElement - The video element
 * @returns {Object} The video.js player instance
 */
function initializeHLSPlayer(videoElement) {
  console.log('Initializing HLS stream');
  
  // Clean up video element
  if (videoElement.srcObject) {
    const tracks = videoElement.srcObject.getTracks();
    tracks.forEach(track => track.stop());
    videoElement.srcObject = null;
  }
  
  // Remove controls from the native video element
  videoElement.controls = false;
  
  // Dispose of any existing player
  if (window.videojs && window.videojs.getPlayers()['chicken-stream']) {
    try {
      window.videojs.getPlayers()['chicken-stream'].dispose();
    } catch (e) {
      console.error('Error disposing existing player:', e);
    }
  }
  
  // Initialize Video.js
  const player = videojs('chicken-stream', {
    fluid: true,
    autoplay: true,
    muted: true,
    liveui: true,
    controls: true,
    controlBar: {
      pictureInPictureToggle: false
    }
  });
  
  // Set HLS source
  player.src({
    src: '/feed/index.m3u8',
    type: 'application/x-mpegURL'
  });
  
  player.play().catch(error => {
    console.error('Error playing HLS stream:', error);
  });
  
  return player;
}

export { initializeHLSPlayer }; 