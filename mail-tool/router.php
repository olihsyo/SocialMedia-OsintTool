<?php
// router.php - PHP built-in server routing
$path = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);

// serve static files directly if they exist
if ($path !== '/' && file_exists(__DIR__ . $path)) {
    return false; 
}

// route to specific php files
if ($path === '/bomb.php') {
    require __DIR__ . '/bomb.php';
    exit;
}

// default fallback to index.html
if ($path === '/') {
    require __DIR__ . '/index.html';
    exit;
}

http_response_code(404);
echo "Not Found";
