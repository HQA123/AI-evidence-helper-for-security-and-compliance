# AI Evidence Helper for Security and Compliance

This project leverages AI to automatically label security and compliance evidence and store it in a knowledge base. You can then search the knowledge base using AI to quickly locate previously uploaded evidence. The supported evidence formats include images, PDFs, documents, and spreadsheets.

## **Prerequisites**

1. **Install Ollama**:  
   Use the `gemma3:27b` and `qwen3-embedding:0.6b` models for the AI tasks.
   
2. **Install Dify**:  
   Set up Dify for workflow management and model integration.

3. **Configuration**:
   - When configuring Ollama, add the following line in the `/etc/systemd/system/ollama.service` file:
     ```bash
     Environment="OLLAMA_HOST=[docker0 ip]:11434"
     ```
   - In Dify, set the base URL for the Ollama model to:
     ```bash
     http://[docker0 ip]:11434
     ```

## **Steps to Use**

### **1. Evidence Import Workflow in Dify**

The first step is to import evidence into the system. The workflow includes various stages, from file conversion to metadata generation and storage.

- **Evidence Import Module**:  
   The images below illustrate the evidence import workflow in Dify.

   ![Evidence Import Workflow](https://github.com/user-attachments/assets/2097e740-548e-404b-82d7-4914f0ccd230)

   - **Conditional Branching**:  
     ![Conditional Branch](https://github.com/user-attachments/assets/3131bcc4-34a9-417b-9578-08fbdb8e439f)

   - **PDF to PNG Conversion**:  
     ![PDF to PNG](https://github.com/user-attachments/assets/70d4539c-aba8-434a-8ca6-08947d3ea96d)

   - **AI Processing (LLM1)**:  
     ![LLM1](https://github.com/user-attachments/assets/47ec8302-fe0a-4ed3-a1a2-679c98441513)

   - **AI Processing (LLM2)**:  
     ![LLM2](https://github.com/user-attachments/assets/49dc2564-bf0b-46b0-a9db-d4de7d29be89)

   - **Persistent Storage**:  
     ![Persistent Storage](https://github.com/user-attachments/assets/27b9ad98-ef38-4cff-a910-1a375ecafd7c)

### **2. Evidence Retrieval Workflow in Dify**

Once the evidence has been processed and stored, you can retrieve it via AI-powered search.

- **Evidence Retrieval Module**:  
   Below is the entire workflow for evidence retrieval in Dify.

   ![Evidence Retrieval Workflow](https://github.com/user-attachments/assets/d3463f28-5638-4e88-bcbc-9a34c35b7570)

   - **LLM-based Search**:  
     ![LLM Search](https://github.com/user-attachments/assets/2c6b9fbf-6584-4965-bb5e-838712204ab8)

### **3. Backend Flask Service**

After importing the evidence, the `metadata.txt` file is imported into Dify’s knowledge base. This enables efficient evidence storage and retrieval through the workflow.

---

## **Collaborate with Us**

For collaboration or inquiries, please contact:  
**qa-huang@foxmail.com**
