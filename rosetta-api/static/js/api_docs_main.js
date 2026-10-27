// Entry point of the /docs page: Swagger UI over the API's OpenAPI document, with the options
// of FastAPI's default page and no online validator.

const container = document.getElementById('swagger-ui');

SwaggerUIBundle({
    url: container.dataset.openapiUrl,
    dom_id: '#swagger-ui',
    layout: 'BaseLayout',
    deepLinking: true,
    showExtensions: true,
    showCommonExtensions: true,
    validatorUrl: null,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
});
