# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Load medical data into Milvus database."""
import numpy as np
from pymilvus import Collection
from pymilvus import CollectionSchema
from pymilvus import DataType
from pymilvus import FieldSchema
from pymilvus import connections
from pymilvus import utility
from sentence_transformers import SentenceTransformer

# replace with your own model based on the size of your data
model = SentenceTransformer("all-MiniLM-L6-v2")

# Connect to Milvus
connections.connect("default", host="localhost", port="19530")

# Define schema for medical records
fields = [
    FieldSchema(name="record_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="patient_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
]

schema = CollectionSchema(fields, "Private medical records for hospital RAG system")

# Drop existing collection if exists
if utility.has_collection("medical_records"):
    utility.drop_collection("medical_records")

# Create collection
collection = Collection("medical_records", schema)

# Sample PRIVATE medical data (fictional but realistic)
medical_records = [{
    "patient_id":
        "PT-2024-001",
    "category":
        "prescription",
    "content": ("Patient prescribed Metformin 500mg twice daily for Type 2 Diabetes. "
                "Monitor blood glucose levels weekly. Patient has history of gastrointestinal "
                "sensitivity - start with 250mg and increase gradually.")
},
                   {
                       "patient_id":
                           "PT-2024-002",
                       "category":
                           "allergy",
                       "content":
                           ("CRITICAL: Patient has severe penicillin allergy - anaphylactic reaction documented. "
                            "Use alternative antibiotics only. Last reaction: 2023-05-15, "
                            "required epinephrine administration.")
                   },
                   {
                       "patient_id":
                           "PT-2024-003",
                       "category":
                           "treatment_protocol",
                       "content": ("Chemotherapy protocol: FOLFOX regimen for Stage III colorectal cancer. "
                                   "Oxaliplatin 85mg/m2 IV day 1, Leucovorin 400mg/m2 IV day 1, "
                                   "5-FU 400mg/m2 IV bolus day 1, then 2400mg/m2 over 46 hours.")
                   },
                   {
                       "patient_id":
                           "PT-2024-004",
                       "category":
                           "lab_results",
                       "content": ("Lab results show elevated liver enzymes: ALT 156 U/L (normal: 7-56), "
                                   "AST 189 U/L (normal: 10-40). Recommend hepatology consultation and "
                                   "avoid hepatotoxic medications.")
                   },
                   {
                       "patient_id":
                           "PT-2024-005",
                       "category":
                           "surgery_notes",
                       "content":
                           ("Post-operative notes: Laparoscopic cholecystectomy completed without complications. "
                            "Patient tolerated procedure well. Prescribed Percocet 5/325mg q6h PRN for pain. "
                            "Follow up in 2 weeks.")
                   },
                   {
                       "patient_id":
                           "PT-2024-006",
                       "category":
                           "mental_health",
                       "content":
                           ("Patient diagnosed with Major Depressive Disorder. Started on Sertraline 50mg daily. "
                            "Previous failed trials with Fluoxetine (GI upset) and Citalopram (QT prolongation). "
                            "Weekly therapy sessions recommended.")
                   },
                   {
                       "patient_id":
                           "PT-2024-007",
                       "category":
                           "pediatric",
                       "content": ("6-year-old with recurrent ear infections. Amoxicillin 400mg/5ml, "
                                   "give 7.5ml twice daily for 10 days. If no improvement in 48 hours, "
                                   "switch to Augmentin. Consider ENT referral for tube placement.")
                   },
                   {
                       "patient_id":
                           "PT-2024-008",
                       "category":
                           "emergency",
                       "content": ("Emergency admission: Acute myocardial infarction. Administered aspirin 325mg, "
                                   "clopidogrel 600mg loading dose, and tPA. Transferred to cath lab for PCI. "
                                   "Stent placed in LAD. Start dual antiplatelet therapy.")
                   },
                   {
                       "patient_id":
                           "PT-2024-009",
                       "category":
                           "chronic_condition",
                       "content": ("Rheumatoid arthritis management: Methotrexate 15mg weekly with folic acid "
                                   "supplementation. Added Humira 40mg subcutaneous every 2 weeks due to "
                                   "inadequate response. Monitor liver function quarterly.")
                   },
                   {
                       "patient_id":
                           "PT-2024-010",
                       "category":
                           "contraindication",
                       "content":
                           ("Patient has G6PD deficiency - AVOID: sulfonamides, aspirin, quinolones, and primaquine. "
                            "Safe alternatives documented in chart. "
                            "Last hemolytic crisis triggered by ciprofloxacin in 2022.")
                   }]

# Generate simple embeddings (in production, use a proper embedding model)
# For demo purposes, we'll create random embeddings
np.random.seed(42)  # For reproducibility

# Prepare data for insertion
patient_ids = [record["patient_id"] for record in medical_records]
contents = [record["content"] for record in medical_records]
categories = [record["category"] for record in medical_records]

embeddings = model.encode(contents).tolist()

# Insert data
data = [patient_ids, contents, categories, embeddings]

collection.insert(data)

# Create index for vector search
index_params = {"metric_type": "L2", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
collection.create_index(field_name="embedding", index_params=index_params)

# Load collection into memory
collection.load()

print(f"Successfully loaded {len(medical_records)} private medical records into Milvus")

# After collection.insert(data)
collection.flush()
print(f"Flushed {collection.num_entities}")
