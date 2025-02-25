import streamlit as st
from PIL import Image
import io
import base64
import google.generativeai as genai
from skimage import exposure
import numpy as np

# Configure Gemini API
genai.configure(api_key="AIzaSyA6-uVGPaaUzTnCqwRMYSA3Ew-S4Q3364o")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(
    page_title="Let Me Cook App",
    page_icon="👨‍🍳",
)

def compress_image(image, max_size=(800, 800), quality=85):
    # Get current dimensions
    width, height = image.size
    
    # Calculate aspect ratio
    aspect_ratio = width / height
    
    # Determine new dimensions while maintaining aspect ratio
    if width > height:
        new_width = min(width, max_size[0])
        new_height = int(new_width / aspect_ratio)
    else:
        new_height = min(height, max_size[1])
        new_width = int(new_height * aspect_ratio)
    
    # Convert to RGB if image is in RGBA mode
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    
    # Resize image
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Compress image
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=quality, optimize=True)
    compressed_image = Image.open(buffer)
    
    return compressed_image

def preprocess_image(image):
    # First compress and resize the image
    compressed_img = compress_image(image)
    
    # Convert PIL Image to numpy array
    img_array = np.array(compressed_img)
    
    # Apply CLAHE with optimized parameters
    clahe = exposure.equalize_adapthist(
        img_array, 
        clip_limit=0.05,
        nbins=128  
    )
    
    # Convert processed image back to PIL format
    clahe_img = Image.fromarray((clahe * 255).astype(np.uint8))
    
    return clahe_img, compressed_img

def analyze_image_gemini(image_bytes):
    # Analyzes an image and extracts ingredients using Gemini
    try:
        # Convert base64 string back to binary data
        img_data = base64.b64decode(image_bytes)
        # Create PIL Image object from binary data
        img = Image.open(io.BytesIO(img_data))

        with st.spinner("🔍 Analyzing image for ingredients..."):
            prompt = """
            Analyze the following image and list the visible food ingredients.
            Provide the list in a comma-separated format, only listing the ingredients.
            Do not include any introductory phrases or explanations.
            If no food is detected in the image simply return "no food".
            """
            response = model.generate_content([prompt, img])
            response.resolve()

        if "no food" in response.text.lower():
            st.error("No food ingredients are visible in the image.")
            return None
        if response.text:
            ingredients_text = response.text.lower()
            ingredients = [item.strip() for item in ingredients_text.split(',') if item.strip()]
            return ingredients
        else:
            st.error("Gemini API returned an empty response for ingredient analysis.")
            return None

    except Exception as e:
        st.error(f"Error during image analysis: {e}")
        return None

def get_recipes_gemini(ingredients):
    #Fetches recipe suggestions using Gemini with formatted output.
    try:
        prompt = f"""
        Suggest 5 numbered recipes using these ingredients: {', '.join(ingredients)}.
        Prioritize Filipino Dishes/Recipes if possible only not necessary.
        Don't show any additional messages or thoughts.
        For each recipe, only provide the following information in a well-structured Markdown format:

        **Recipe Name:** [Name of the Recipe]

        **Difficulty Level:** [Easy, Medium, or Hard]

        **Cooking Time:** [Estimated cooking time, e.g., 30 minutes]

        **Ingredients:**
        - [Ingredient 1]
        - [Ingredient 2]
        - ...

        **Instructions:**
        1. [Step 1]
        2. [Step 2]
        3. ...

        Make sure each recipe is clearly separated by a horizontal rule (---).
        """
        with st.spinner("🍳 Generating recipes..."):
            response = model.generate_content(prompt)
            response.resolve()

        if response.text:
            return response.text
        else:
            st.error("Gemini API returned an empty response for recipe generation.")
            return None

    except Exception as e:
        st.error(f"🚨 Error getting recipes: {e}")
        return None

def main():
    # Initialize session state
    if 'analyzed_ingredients' not in st.session_state:
        st.session_state.analyzed_ingredients = None
    if 'current_image_bytes' not in st.session_state:
        st.session_state.current_image_bytes = None
    if 'original_image' not in st.session_state:
        st.session_state.original_image = None
    if 'processed_image' not in st.session_state:
        st.session_state.processed_image = None

    # st.image("./lmc.png", width=800)  # Changed from use_container_width to width parameter
    st.title("Let Me Cook! 👨🏻‍🍳🔥")
    st.write("Stop wasting food and start creating. Take a photo of your ingredients and receive instant recipe recommendation.")

    source = st.radio("Select Image Source", ("Upload an image 🖼️", "Use Camera 📸"))

    if source == "Upload an image 🖼️":
        uploaded_file = st.file_uploader("Upload an image of ingredients", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            # Only process new images
            current_bytes = uploaded_file.getvalue()
            if st.session_state.current_image_bytes != current_bytes:
                st.session_state.current_image_bytes = current_bytes
                image = Image.open(uploaded_file)
                
                # Apply preprocessing and store in session state
                clahe_img, compressed_img = preprocess_image(image)
                st.session_state.original_image = image
                st.session_state.processed_image = clahe_img
                
                # Analyze new image
                buffer = io.BytesIO()
                compressed_img.save(buffer, format="JPEG")
                image_bytes = base64.b64encode(buffer.getvalue()).decode("utf-8")
                st.session_state.analyzed_ingredients = analyze_image_gemini(image_bytes)

    else:
        image_file = st.camera_input("Take a picture")
        if image_file is not None:
            # Only process new images
            current_bytes = image_file.getvalue()
            if st.session_state.current_image_bytes != current_bytes:
                st.session_state.current_image_bytes = current_bytes
                image = Image.open(image_file)
                
                # Apply preprocessing and store in session state
                clahe_img, compressed_img = preprocess_image(image)
                st.session_state.original_image = image
                st.session_state.processed_image = clahe_img
                
                # Convert processed image to JPEG bytes
                buffer = io.BytesIO()
                compressed_img.save(buffer, format="JPEG")
                # Convert binary image data to base64 string for API transmission
                image_bytes = base64.b64encode(buffer.getvalue()).decode("utf-8")
                st.session_state.analyzed_ingredients = analyze_image_gemini(image_bytes)

    # Display images if they exist in session state
    if st.session_state.original_image is not None:
        st.subheader("Image Processing Results ⚙️")
        col1, col2 = st.columns(2)
        with col1:
            st.write("Original Image")
            st.image(st.session_state.original_image, use_container_width=True)
        with col2:
            st.write("Processed Image")
            st.image(st.session_state.processed_image, use_container_width=True)

    # Use stored ingredients for selection and recipe generation
    if st.session_state.analyzed_ingredients:
        st.subheader("Recognized Ingredients: 👀")
        
        with st.expander("Select Ingredients", expanded=True):
            st.write("Choose the ingredients you want to use in your recipe:")
            selected_ingredients = {}
            
            cols = st.columns(3)
            for index, ingredient in enumerate(st.session_state.analyzed_ingredients):
                col_idx = index % 3
                with cols[col_idx]:
                    selected_ingredients[ingredient] = st.checkbox(
                        f"{ingredient.capitalize()}", 
                        value=True,
                        key=f"ingredient_{index}"
                    )
            
        if st.button("Get Recipes 🍽️"):
            final_ingredients = [
                ingredient for ingredient, selected in selected_ingredients.items() 
                if selected
            ]
            
            if final_ingredients:
                st.write("Selected ingredients:", ", ".join(final_ingredients))
                recipe_text = get_recipes_gemini(final_ingredients)
                if recipe_text:
                    st.subheader("Recipe Suggestions: 😋")
                    recipes = recipe_text.split("---")
                    for recipe in recipes:
                        start = recipe.find("Recipe")
                        end = recipe.find("Ingredients")
                        with st.expander(f"{recipe[start:end].replace('*','')}"):
                            st.write(recipe.replace(recipe[start:end].strip(),""))
            else:
                st.warning("Please select at least one ingredient to get recipes.")
    
    st.caption("Created by Johann.dev")

main()